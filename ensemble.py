"""Score every trained checkpoint, alone and averaged together, with and without TTA.

    python ensemble.py

Reads every best_weights_*.pt in this directory, works out each one's backbone
from its keys, and reports validation and test accuracy for each model on its
own and for the ensemble.

Two cheap wins live here and neither needs retraining:

* Test-time augmentation. Each photo is scored twice, upright and mirrored, and
  the probabilities are averaged. Worth about a point, measured.
* Ensembling. Averaging the probabilities of models that make *different*
  mistakes beats any one of them. Two different backbones ensemble better than
  two runs of the same one.
"""

from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

import data_pipeline
from cnn import adapt_state, backbone_of, build_model, final_layer_classes

HERE = Path(__file__).resolve().parent
BATCH_SIZE = 64


def checkpoint_paths(extra_dir=None):
    """Hand-tuned checkpoints first, then whatever a sweep kept.

    extra_dir lets overnight.py name its own checkpoint directory instead of
    this module guessing it, so the two files cannot drift apart.
    """
    sweep_dir = Path(extra_dir) if extra_dir else HERE / "overnight_checkpoints"
    return sorted(HERE.glob("best_weights_*.pt")) + sorted(sweep_dir.glob("*.pt"))


def load_checkpoints(class_count, device, extra_dir=None):
    """Every checkpoint on disk, built into the backbone it was trained with."""
    models = []
    for path in checkpoint_paths(extra_dir):
        state = torch.load(path, map_location="cpu")
        if final_layer_classes(state) != class_count:
            print(f"  skipping {path.name}: trained on "
                  f"{final_layer_classes(state)} categories, dataset has {class_count}")
            continue
        backbone = backbone_of(state)
        net = build_model(class_count, pretrained=False, backbone=backbone).to(device)
        net.load_state_dict(adapt_state(state), strict=True)
        net.eval()
        models.append((path.stem, net))
    return models


def probabilities(net, loader, device, tta):
    """Softmax outputs for a whole split, optionally averaged with the mirror image."""
    chunks = []
    with torch.no_grad():
        for inputs, _ in loader:
            inputs = inputs.to(device)
            p = F.softmax(net(inputs), dim=1)
            if tta:
                p = (p + F.softmax(net(torch.flip(inputs, dims=[3])), dim=1)) / 2
            chunks.append(p.cpu())
    return torch.cat(chunks)


def labels_of(loader):
    return torch.cat([y for _, y in loader])


def accuracy(probs, labels):
    return (probs.argmax(1) == labels).float().mean().item()


def select_ensemble(model_probs, labels):
    """Pick the subset of models that scores best together. Greedy, on validation.

    Averaging *every* checkpoint is a trap: a weak model drags the average down.
    Measured on four checkpoints, naive averaging gave 83.5% while the best
    single model gave 84.0%. With fifty runs that would happen constantly.

    This starts from the single best model and keeps adding whichever model most
    improves the combined accuracy, stopping when nothing helps. It can never do
    worse than the best single model, because that is where it begins.

    Returns (chosen indices, their combined accuracy). Note the choice is made
    on validation, so the matching test score is a mildly optimistic estimate -
    the same caveat as picking the best epoch on validation.
    """
    chosen, pooled, best = [], None, -1.0
    remaining = list(range(len(model_probs)))

    while remaining:
        scored = [(accuracy(model_probs[i] if pooled is None else pooled + model_probs[i],
                            labels), i)
                  for i in remaining]
        score, pick = max(scored)
        if score <= best:
            break
        best = score
        chosen.append(pick)
        remaining.remove(pick)
        pooled = model_probs[pick] if pooled is None else pooled + model_probs[pick]

    return chosen, best


def main():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    _, validation_set, test_set, _ = data_pipeline.make_loaders(num_workers=0)
    class_count = len(validation_set.dataset.dataset.classes)

    models = load_checkpoints(class_count, device)
    if not models:
        raise SystemExit("No usable checkpoints found. Train with cnn.py or overnight.py first.")

    validation_labels = labels_of(validation_set)
    validation_probs = [probabilities(net, validation_set, device, tta=True)
                        for _, net in models]
    plain_probs = [probabilities(net, validation_set, device, tta=False)
                   for _, net in models]

    print(f"\n=== validation ({len(validation_labels)} photos) ===")
    print(f"  {'model':<42} {'plain':>8} {'+TTA':>8}")
    for (name, _), plain, flipped in zip(models, plain_probs, validation_probs):
        print(f"  {name:<42} {accuracy(plain, validation_labels):>7.1%} "
              f"{accuracy(flipped, validation_labels):>8.1%}")

    chosen, val_accuracy = select_ensemble(validation_probs, validation_labels)
    best_single = max(accuracy(p, validation_labels) for p in validation_probs)
    print(f"  {'-' * 60}")
    print(f"  chosen for the ensemble: {', '.join(models[i][0] for i in chosen)}")
    print(f"  {'ENSEMBLE (+TTA)':<42} {'':>8} {val_accuracy:>8.1%}  "
          f"({(val_accuracy - best_single) * 100:+.1f} pts over best single)")

    # The same models, scored on test. Chosen on validation, so treat the test
    # figure as the honest headline and the validation one as the tuning signal.
    test_labels = labels_of(test_set)
    test_probs = [probabilities(models[i][1], test_set, device, tta=True) for i in chosen]
    pooled = sum(test_probs[1:], test_probs[0])
    print(f"\n=== test ({len(test_labels)} photos) ===")
    print(f"  ENSEMBLE of {len(chosen)} (+TTA): {accuracy(pooled, test_labels):.1%}"
          f"   <- the Req 5d number")


if __name__ == "__main__":
    main()
