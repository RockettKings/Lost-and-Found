import os
from datetime import datetime
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import models

import data_pipeline


class Net(nn.Module):
    """The hand-built CNN. Kept as the Req 5d from-scratch baseline.

    Best result: 51.0% test accuracy, at 128x128 with SGD lr=0.05, momentum 0.9,
    nesterov, weight decay 5e-4, heavy augmentation, 150 epochs. Superseded by
    build_model() below, but the number is a legitimate experimental result and
    this class is what produced it.
    """

    def __init__(self, class_count):
        super().__init__()
        # Four blocks, channels doubling each time. 3x3 kernels stacked deep
        # cover the same receptive field as one 5x5 with fewer parameters and a
        # nonlinearity between every step.
        #
        # Widened from 32/64/128/256 on Nov 18: at 397K parameters the model was
        # underfitting, stuck at 64% training accuracy with validation loss still
        # falling. 64/128/256/512 brings it to ~1.6M, which is enough capacity
        # for 31 classes while staying small enough to ship.
        self.conv1 = nn.Conv2d(3, 64, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(64)
        self.conv2 = nn.Conv2d(64, 128, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(128)
        self.conv3 = nn.Conv2d(128, 256, 3, padding=1)
        self.bn3 = nn.BatchNorm2d(256)
        self.conv4 = nn.Conv2d(256, 512, 3, padding=1)
        self.bn4 = nn.BatchNorm2d(512)
        self.pool = nn.MaxPool2d(2, 2)

        # Averages each channel over the whole frame, so a wallet reads as a
        # wallet wherever it sits in the photo. This replaces the 44,944-wide
        # flatten that used to feed a 5.39M parameter fully-connected layer.
        self.global_pool = nn.AdaptiveAvgPool2d(1)

        # Back up to 0.4. 0.1 was right while the model was underfitting; once
        # widened it overfit hard (78.7% clean train against 47.7% validation),
        # and a wider model can absorb more dropout than a narrow one.
        self.dropout = nn.Dropout(0.4)
        self.fc = nn.Linear(512, class_count)

    def forward(self, x):
        x = self.pool(F.relu(self.bn1(self.conv1(x))))
        x = self.pool(F.relu(self.bn2(self.conv2(x))))
        x = self.pool(F.relu(self.bn3(self.conv3(x))))
        x = self.pool(F.relu(self.bn4(self.conv4(x))))
        x = self.global_pool(x)
        x = torch.flatten(x, 1) # flatten all dimensions except batch
        x = self.dropout(x)
        x = self.fc(x)
        return x


# Stock ResNet18 ships with no dropout, which left the previous run with no
# regularization in the classifier at all.
DROPOUT = 0.3


def _use_certifi_bundle():
    """Point Python's TLS verification at certifi's CA bundle.

    This Python was installed without running the macOS "Install Certificates"
    step, so it has no CA bundle of its own and the weights download fails with
    CERTIFICATE_VERIFY_FAILED. Setting this before the download fixes it without
    needing an environment variable on every run. Does nothing if the variable
    is already set or certifi is not installed.
    """
    if os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi
    except ImportError:
        return
    os.environ["SSL_CERT_FILE"] = certifi.where()


# Which torchvision backbone to fine-tune. EfficientNet-B0 has a better
# ImageNet top-1 (77.7% vs ResNet18's 69.8%) with less than half the parameters
# (5.3M vs 11.2M), so it starts from stronger features and has less room to
# memorize. Swapping this is how to run the two as separate experiments, and
# two different backbones also make a better ensemble than two of the same.
BACKBONE = "efficientnet_b0"   # or "resnet18"


def build_model(class_count, pretrained=True, backbone=None):
    """Requirements R1, R2, R6: a pretrained backbone with our own final layer.

    pretrained=True downloads the ImageNet weights (about 45 MB, cached under
    ~/.cache/torch) and is what training uses. The whole point is these weights:
    loading the architecture empty gives a worse result than the hand-built CNN,
    because it is a far bigger model on the same small dataset.

    pretrained=False builds the same architecture with random weights, for the
    app to load our fine-tuned state_dict into. Requirement R6: the deployed app
    must never download anything at startup.

    The final layer's output count comes from the dataset, never a literal. A
    hardcoded count is what made five categories unpostable in an earlier run.
    ResNet18's classifier is named `fc`, so a saved state_dict still carries
    `fc.weight` with shape (class_count, 512) - the same key review_errors.py
    checks for.
    """
    if pretrained:
        _use_certifi_bundle()
    backbone = backbone or BACKBONE

    # Dropout added Nov 19. Stock ResNet18 has none at all, so the first
    # fine-tuning run had no regularization in the classifier and memorized the
    # training set by epoch 4. Wrapping the classifier renames the saved weights
    # from "fc.weight" to "fc.1.weight"; final_layer_classes() reads either.
    if backbone == "resnet18":
        model = models.resnet18(
            weights=models.ResNet18_Weights.DEFAULT if pretrained else None)
        model.fc = nn.Sequential(
            nn.Dropout(DROPOUT),
            nn.Linear(model.fc.in_features, class_count),
        )
    elif backbone == "efficientnet_b0":
        model = models.efficientnet_b0(
            weights=models.EfficientNet_B0_Weights.DEFAULT if pretrained else None)
        # EfficientNet already ends in Dropout + Linear, so only the Linear is
        # replaced and the dropout rate is set to ours.
        model.classifier[0].p = DROPOUT
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, class_count)
    else:
        raise ValueError(f"Unknown backbone {backbone!r}.")
    return model


def final_layer_classes(state):
    """How many categories a saved checkpoint predicts.

    Handles both spellings: "fc.weight" from the pre-dropout architecture and
    "fc.1.weight" from the current one.
    """
    for key in ("fc.1.weight", "fc.weight", "classifier.1.weight"):
        if key in state:
            return state[key].shape[0]
    raise KeyError("No final linear layer found in the checkpoint.")


def backbone_of(state):
    """Which backbone a checkpoint was trained with, read from its keys."""
    return "efficientnet_b0" if "classifier.1.weight" in state else "resnet18"


def head_module(model):
    """The classifier block, whatever this backbone calls it.

    ResNet names it `fc`, EfficientNet names it `classifier`. Hardcoding `fc`
    is what crashed the first EfficientNet run before epoch 1.
    """
    return model.fc if hasattr(model, "fc") else model.classifier


def adapt_state(state):
    """Rename a pre-dropout checkpoint's classifier keys to the current layout.

    Adding Dropout moved the classifier from `fc` to `fc.1`. The Linear itself is
    unchanged, so renaming the two keys is enough to load an older checkpoint.

    Always load with strict=True after this. Using strict=False instead would
    silently leave the final layer at its random initialization, which scores at
    chance and looks like a broken model rather than a bad load.
    """
    if "fc.weight" not in state:
        return state
    adapted = dict(state)
    adapted["fc.1.weight"] = adapted.pop("fc.weight")
    adapted["fc.1.bias"] = adapted.pop("fc.bias")
    return adapted


RESULTS_PATH = Path(__file__).resolve().parent / "documents" / "model-results.md"

# Requirement 5d wants a record of *each* experiment. RESULTS_PATH holds the
# detailed per-epoch table for the current run and is overwritten each time, so
# one summary row per finished run is appended here instead.
EXPERIMENTS_PATH = Path(__file__).resolve().parent / "documents" / "model-experiments.md"

# Re-added Nov 18. Without it the best epoch's model is gone when the process
# exits - the 47.7% run's epoch 67 weights were lost that way. Gitignored.
# One file per backbone, so training EfficientNet does not destroy the ResNet
# run. ensemble.py averages every best_weights_*.pt it finds.
WEIGHTS_PATH = Path(__file__).resolve().parent / f"best_weights_{BACKBONE}.pt"

# Raised Nov 19 from 50. With the light augmentation, more epochs were pointless
# because training accuracy was already 100%. Now that the photos are harder to
# memorize, the extra epochs have something to do.
EPOCHS = 60

# 0 disables early stopping. Disabled Nov 19: it kept cutting runs off before
# the cosine schedule finished. The Nov 19 19:36 run peaked at epoch 52 and
# stopped at 72, with the learning rate still around a third of its starting
# value - so the model never reached the low-rate settling at the end of the
# schedule, which is often where the last point or two of accuracy appears.
#
# Early stopping exists to save time, and time is not the constraint here. The
# best checkpoint is saved on its own, so running the full schedule costs
# nothing but minutes. Set this back to 20 or 30 if a run needs a time cap.
EARLY_STOPPING_PATIENCE = 0

# Requirement R4: two learning rates. The backbone already holds good features
# and only needs nudging, so it moves slowly; the new final layer starts from
# random weights and has everything to learn, so it moves 10x faster. Training
# the whole network at the head's rate would wreck the pretrained features in
# the first few batches, which is the most common way fine-tuning fails.
HEAD_LEARNING_RATE = 1e-3
# Lowered Nov 19 from 1e-4. Fine-tuning all 11.2M backbone parameters on 5,271
# photos gives the network a lot of freedom to memorize; a slower backbone keeps
# more of the ImageNet features intact and shifts the learning into the head.
BACKBONE_LEARNING_RATE = 1e-4

# AdamW applies weight decay correctly, unlike plain Adam where it interacts
# badly with the adaptive step sizes. Raised Nov 19 from 1e-4 as a third brake
# on memorization, alongside dropout and the heavier augmentation.
WEIGHT_DECAY = 1e-4

# Tier 2: stops the model from driving one logit to certainty, which helps it
# generalize when there are only ~170 training photos per class.
LABEL_SMOOTHING = 0.1

# MixUp strength. Beta(a, a) with a=0.2 mostly draws blends near 0 or 1, so most
# batches stay close to a real photo and only some are strongly mixed - the
# usual setting for fine-tuning. Raise toward 0.4 for more mixing, set to 0 to
# turn MixUp off and reproduce the earlier runs.
MIXUP_ALPHA = 0.0

# How often to score the training set the same way validation is scored: eval
# mode, no dropout, no augmentation. Only this number is comparable to validation
# accuracy, and the difference between the two is the real overfitting gap.
# Doing it every epoch would roughly double epoch time, so it runs periodically.
CLEAN_TRAIN_EVERY = 10


def class_weights(training_set, class_count):
    """Weight each class by how rare it is in the training split.

    The dataset is close to balanced since the Nov 18 refresh - 26 of 31 classes
    hold 250 photos, and only binder (172) and sweatshirt (208) dip - so these
    weights are mild, roughly 0.97 to 1.42. They still matter if a later dataset
    is lopsided again, and they cost nothing when it is not.

    Averaged over the photos rather than over the classes these weights come to
    exactly 1.0, so the loss stays on its usual scale.
    """
    counts = torch.zeros(class_count)
    for index in training_set.indices:
        counts[training_set.dataset.targets[index]] += 1
    return counts.sum() / (class_count * counts)


def evaluate(net, loader, criterion, device, class_count):
    """Score a loader in eval mode. Returns (loss per photo, accuracy, confusion).

    eval() switches dropout off and makes BatchNorm use its running statistics.
    no_grad() skips building the backward graph, which is never used here.

    confusion[true][predicted] counts photos, which is the Req 5d confusion
    matrix. Accumulating it costs one scatter per batch, so it runs every time
    rather than only when asked for.
    """
    net.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    confusion = torch.zeros(class_count, class_count, dtype=torch.long)

    with torch.no_grad():
        for inputs, labels in loader:
            inputs, labels = inputs.to(device), labels.to(device)

            outputs = net(inputs)
            loss = criterion(outputs, labels)
            predicted = outputs.argmax(1)

            total_loss += loss.item() * labels.size(0)
            correct += (predicted == labels).sum().item()
            total += labels.size(0)

            for true_label, predicted_label in zip(labels.cpu(), predicted.cpu()):
                confusion[true_label, predicted_label] += 1

    return total_loss / total, correct / total, confusion


def worst_pairs(confusion, classes, top=15):
    """The most-confused (true, predicted) pairs, ignoring correct answers.

    Req 5d wants a confusion matrix; 31x31 is too wide to read in markdown, so
    this reports the pairs that actually cost accuracy. If the worst pairs are
    look-alikes (eyeglasses/sunglasses, binder/notebook/textbook), the fix is
    resolution or cleaner labels rather than more capacity.
    """
    pairs = []
    for true_index in range(len(classes)):
        for predicted_index in range(len(classes)):
            if true_index == predicted_index:
                continue
            count = int(confusion[true_index, predicted_index])
            if count:
                pairs.append((count, classes[true_index], classes[predicted_index]))
    pairs.sort(reverse=True)
    return pairs[:top]


def write_results(settings, rows, best_accuracy, best_epoch, confusion_pairs=None):
    """Rewrite the markdown results log with the numbers measured so far.

    Rewritten after every epoch rather than at the end, so an interrupted run
    still leaves a readable log.
    """
    lines = [
        "# Model Results, Req 5d",
        "",
        "Written by `cnn.py`. **The next run overwrites this file** - copy or rename",
        "it before starting another experiment if you want to keep these numbers.",
        "",
        "## Settings",
        "",
        "| Setting | Value |",
        "| --- | --- |",
    ]
    lines += [f"| {name} | {value} |" for name, value in settings.items()]
    lines += [
        "",
        "## Per epoch",
        "",
        "| Epoch | Train loss | Train acc | Val loss | Val acc | Clean train acc | Gap | Best so far |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        clean = row["clean_train_accuracy"]
        clean_cell = f"{clean:.1%}" if clean is not None else ""
        # x100 because these are fractions, not percentages. Without it a 34
        # point gap printed as "+0.3 pts" and hid the overfitting completely.
        gap_cell = f"{(clean - row['val_accuracy']) * 100:+.1f} pts" if clean is not None else ""
        lines.append(
            f"| {row['epoch']} | {row['train_loss']:.3f} | {row['train_accuracy']:.1%} "
            f"| {row['val_loss']:.3f} | {row['val_accuracy']:.1%} "
            f"| {clean_cell} | {gap_cell} | {'yes' if row['best'] else ''} |"
        )
    lines += [
        "",
        f"Best validation accuracy **{best_accuracy:.1%}**, reached at epoch {best_epoch}.",
        "",
        "## Reading the two training accuracies",
        "",
        "**Train acc** is measured while training: dropout on, augmentation applied.",
        "It is handicapped on purpose and is not comparable to validation accuracy.",
        "",
        "**Clean train acc** is the same photos scored the way validation is scored:",
        "eval mode, no dropout, no augmentation. Only this number is comparable, and",
        "**Gap** is clean train minus validation - the real overfitting gap.",
        "",
        "- Clean train low (say under 80%) means the model still cannot fit its own",
        "  training data. That is underfitting: add capacity, cut regularization, or",
        "  raise resolution.",
        "- Clean train high with a large gap means it fits training and fails to",
        "  generalize. That is overfitting: add regularization or more photos.",
        "",
    ]

    if confusion_pairs:
        lines += [
            "## Worst confusions at the best epoch",
            "",
            "Validation set, `true -> predicted`, from the Req 5d confusion matrix.",
            "",
            "| Count | True label | Predicted as |",
            "| --- | --- | --- |",
        ]
        lines += [f"| {count} | {true_label} | {predicted_label} |"
                  for count, true_label, predicted_label in confusion_pairs]
        lines += [
            "",
            "Look-alike pairs dominating this table points at resolution or label",
            "noise. Unrelated pairs dominating points at capacity.",
            "",
        ]
    RESULTS_PATH.write_text("\n".join(lines))


def append_experiment(settings, best_accuracy, best_epoch, epochs_run):
    """Add one summary row for this run to the cumulative Req 5d log.

    Appends rather than rewrites, so finishing a new run never erases the
    record of the previous ones.
    """
    header = (
        "# Experiment Log, Req 5d\n"
        "\n"
        "One row per finished training run. Per-epoch detail for the most recent\n"
        "run is in [model-results.md](model-results.md), which is overwritten each\n"
        "time. Test accuracy is measured separately with `review_errors.py`.\n"
        "\n"
        "| Run started | Architecture | Image | Epochs | Optimizer | Augmentation | Best val | At epoch |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )
    if not EXPERIMENTS_PATH.exists():
        EXPERIMENTS_PATH.write_text(header)

    row = (f"| {settings['run started']} | {settings['architecture']} "
           f"| {settings['image size']} | {epochs_run} of {settings['epochs']} "
           f"| {settings['optimizer']} | {settings['augmentation']} "
           f"| **{best_accuracy:.1%}** | {best_epoch} |\n")
    with EXPERIMENTS_PATH.open("a") as log:
        log.write(row)


def main(training_seed=None, backbone=None, weights_path=None, epochs=None):
    """Train one model and return (best validation accuracy, best epoch).

    Every argument defaults to the module constant, so `python cnn.py` behaves
    exactly as before. sweep.py overrides them to run many models in a row.

    training_seed varies the weight init, the shuffle order and the augmentation
    draws WITHOUT touching the split: the split is drawn by Random(SEED) inside
    data_pipeline, which torch's generator never touches. That is what makes
    several runs comparable to each other and safe to ensemble - they all share
    one validation set and none of them has seen another's.
    """
    training_seed = data_pipeline.SEED if training_seed is None else training_seed
    backbone = backbone or BACKBONE
    weights_path = Path(weights_path) if weights_path else WEIGHTS_PATH
    epochs = epochs or EPOCHS

    torch.manual_seed(training_seed)

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

    trainLoader,evalLoader,testLoader,cleanTrainLoader = data_pipeline.make_loaders()

    # Subset -> ImageFolder -> the 29 sorted folder names.
    categories = trainLoader.dataset.dataset.classes

    net = build_model(len(categories), backbone=backbone).to(device)
    criterion = nn.CrossEntropyLoss(
        weight=class_weights(trainLoader.dataset, len(categories)).to(device),
        label_smoothing=LABEL_SMOOTHING,
    )

    # Two parameter groups so the head and the backbone anneal from different
    # starting rates. Identity is used to split them because a parameter has no
    # name once it is in the list.
    # head_module() because EfficientNet calls this `classifier`, not `fc`.
    # Dropout contributes no parameters, so this is effectively the Linear.
    head_parameters = list(head_module(net).parameters())
    head_parameter_ids = {id(parameter) for parameter in head_parameters}
    backbone_parameters = [parameter for parameter in net.parameters()
                           if id(parameter) not in head_parameter_ids]

    optimizer = optim.AdamW([
        {"params": backbone_parameters, "lr": BACKBONE_LEARNING_RATE},
        {"params": head_parameters, "lr": HEAD_LEARNING_RATE},
    ], weight_decay=WEIGHT_DECAY)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    settings = {
        "run started": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "architecture": f"{backbone}, ImageNet pretrained, final layer replaced, dropout {DROPOUT}",
        "parameters": f"{sum(p.numel() for p in net.parameters()):,}",
        "categories": len(categories),
        "image size": f"{data_pipeline.IMAGE_SIZE}x{data_pipeline.IMAGE_SIZE}",
        "split": f"{len(trainLoader.dataset)} train / {len(evalLoader.dataset)} val / {len(testLoader.dataset)} test",
        "batch size": data_pipeline.BATCH_SIZE,
        "epochs": epochs,
        "optimizer": f"AdamW head lr={HEAD_LEARNING_RATE} backbone lr="
                     f"{BACKBONE_LEARNING_RATE}, weight decay {WEIGHT_DECAY}, "
                     f"cosine annealing",
        "loss": f"CrossEntropyLoss, class weighted, label smoothing {LABEL_SMOOTHING}",
        "augmentation": f"rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha {MIXUP_ALPHA}",
        "clean train scored": f"every {CLEAN_TRAIN_EVERY} epochs and on the last",
        "early stopping": (f"val accuracy flat for {EARLY_STOPPING_PATIENCE} epochs"
                           if EARLY_STOPPING_PATIENCE else "disabled, full schedule"),
        "split seed": data_pipeline.SEED,
        "training seed": training_seed,
        "device": device.type,
    }

    rows = []
    best_val_accuracy = 0.0
    best_epoch = 0
    best_confusion_pairs = None
    # Early stopping now watches validation ACCURACY, not loss. In the Nov 19
    # 18:51 run validation loss bottomed at epoch 23 while accuracy peaked at
    # 13, so the two move on different schedules: cross-entropy loss rises when
    # the model grows more confident about the photos it gets wrong, even while
    # accuracy holds or improves. Accuracy is what we actually want, and it is
    # already what the checkpoint is chosen on.
    epochs_since_val_accuracy_improved = 0

    # Only built when MixUp is on: Beta(0, 0) is not a valid distribution, so
    # constructing it unconditionally crashes whenever MIXUP_ALPHA is 0.
    mixup_distribution = (torch.distributions.Beta(MIXUP_ALPHA, MIXUP_ALPHA)
                          if MIXUP_ALPHA > 0 else None)

    for epoch in range(epochs):

        net.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for inputs, labels in trainLoader:
            inputs, labels = inputs.to(device), labels.to(device)

            # MixUp. Every regularizer tried so far acts on pixels, and the
            # model still memorized: clean training accuracy reached 99.8% with
            # rotation, cropping, jitter, grayscale, erasing, dropout 0.4 and
            # weight decay 1e-3 all switched on.
            #
            # MixUp works on the label instead. Each batch is blended with a
            # shuffled copy of itself, and the loss is blended by the same
            # fraction, so the target for a given image is never the same twice.
            # There is no fixed answer left to memorize.
            blend = 1.0
            shuffled_labels = labels
            if MIXUP_ALPHA > 0:
                blend = float(mixup_distribution.sample())
                order = torch.randperm(labels.size(0), device=device)
                inputs = blend * inputs + (1.0 - blend) * inputs[order]
                shuffled_labels = labels[order]

            # zero the parameter gradients
            optimizer.zero_grad()

            # forward + backward + optimize
            outputs = net(inputs)
            loss = (blend * criterion(outputs, labels)
                    + (1.0 - blend) * criterion(outputs, shuffled_labels))
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * labels.size(0)

            # Scored against the primary label only, so with MixUp on this reads
            # lower than the model's real ability. Clean train acc is the honest
            # measure; this column is only useful for spotting a stalled run.
            correct += (outputs.argmax(1) == labels).sum().item()
            total += labels.size(0)

        train_loss = running_loss / total
        train_accuracy = correct / total

        class_count = len(categories)
        val_loss, val_accuracy, confusion = evaluate(
            net, evalLoader, criterion, device, class_count)

        # The training set scored the way validation is, so the two comparable.
        # Skipped on most epochs because it roughly doubles the epoch's work.
        clean_train_accuracy = None
        if (epoch + 1) % CLEAN_TRAIN_EVERY == 0 or epoch + 1 == epochs:
            _, clean_train_accuracy, _ = evaluate(
                net, cleanTrainLoader, criterion, device, class_count)

        # Steps the learning rate down once per epoch, not once per batch.
        scheduler.step()

        is_best = val_accuracy > best_val_accuracy
        if is_best:
            best_val_accuracy = val_accuracy
            best_epoch = epoch + 1
            best_confusion_pairs = worst_pairs(confusion, categories)
            # state_dict() saves the weights only, so the file stays loadable
            # even after the Net class changes.
            torch.save(net.state_dict(), weights_path)

        epochs_since_val_accuracy_improved = 0 if is_best else epochs_since_val_accuracy_improved + 1

        clean_note = ""
        if clean_train_accuracy is not None:
            clean_note = (f"  clean train {clean_train_accuracy:.1%} "
                          f"(gap {clean_train_accuracy - val_accuracy:+.1%})")

        print(f"epoch {epoch + 1:>3}/{epochs}  "
              f"train loss {train_loss:.3f} acc {train_accuracy:.1%}  "
              f"val loss {val_loss:.3f} acc {val_accuracy:.1%}"
              f"{clean_note}"
              f"{'  <- best, saved' if is_best else ''}")

        rows.append({
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "train_accuracy": train_accuracy,
            "val_loss": val_loss,
            "val_accuracy": val_accuracy,
            "clean_train_accuracy": clean_train_accuracy,
            "best": is_best,
        })
        write_results(settings, rows, best_val_accuracy, best_epoch,
                      best_confusion_pairs)

    append_experiment(settings, best_val_accuracy, best_epoch, len(rows))

    print(f"Finished Training, best validation accuracy {best_val_accuracy:.1%} "
          f"at epoch {best_epoch}")
    print(f"Experiment row appended to {EXPERIMENTS_PATH}")
    print(f"Best weights written to {weights_path}")
    print(f"Results written to {RESULTS_PATH}")
    return best_val_accuracy, best_epoch


# Required because make_loaders uses worker processes. macOS spawns them, which
# re-imports this module, and without the guard every worker would start its own
# training run.
if __name__ == "__main__":
    main()
