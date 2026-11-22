from pathlib import Path
from random import Random

from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms


# Requirement R3: 224 is what ImageNet backbones were trained on, and the
# pretrained features are strongest at the size they were learned at. The
# normalization below already uses the ImageNet statistics the backbone expects,
# so the size is the only thing that had to change.
IMAGE_SIZE = 224

# Augmentation history, settled Nov 19 by measurement:
#
#   light  (this stack)                       val 78.8%
#   heavy  (rotate10, crop 0.5, grayscale,
#           erasing 0.25, jitter 0.3)         val 77.9%
#   heavy + MixUp 0.2                         val 77.7%
#
# All three fall inside the +/-1.2 point noise band of a 1,115 photo validation
# split, so the heavy stacks bought nothing. None of them stopped the model
# memorizing either - clean training accuracy still reached 99.7% - which points
# at label noise rather than augmentation as the binding constraint. Keeping the
# configuration that measured best.
training_transformation = transforms.Compose([
    transforms.RandomResizedCrop(IMAGE_SIZE, scale=(0.7, 1.0)),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.02),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

validation_transformation = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# Absolute, so the script runs from any working directory.
DATASET_ROOT = Path(__file__).resolve().parent / "documents" / "dataset"

# Requirement 5c: the split must be reproducible, so the shuffle is seeded.
SEED = 581

TRAIN_FRACTION = 0.70
VALIDATION_FRACTION = 0.15
# Test takes whatever is left, so rounding never drops or duplicates a photo.

# How many photos a DataLoader hands out at a time.
BATCH_SIZE = 32

# Tier 3: JPEG decode and the transforms used to run single-threaded in the main
# process while the GPU waited. Workers do that decoding in parallel instead.
# Anything importing this module must guard its own top-level code with
# `if __name__ == "__main__":` - macOS spawns workers, which re-import the main
# module, and an unguarded training loop would restart inside every worker.
NUM_WORKERS = 4

# splits dataset into training, validation, testing
def split_dataset(root=DATASET_ROOT, seed=SEED):
    """Return (training, validation, test) subsets, split within every class.

    Each class is split separately so all three sets hold the same class mix.
    Two ImageFolder instances read the same files in the same order, so one set of
    indices addresses both: training comes from the augmented copy, validation and
    test from the deterministic one, which keeps augmentation out of scoring.

    The label strings are on the returned subsets as `.dataset.classes`.
    """
    training_base = datasets.ImageFolder(root, transform=training_transformation)
    evaluation_base = datasets.ImageFolder(root, transform=validation_transformation)

    # ImageFolder.targets is the label index of every photo, in sample order.
    photos_by_label = {}
    for index, label in enumerate(training_base.targets):
        photos_by_label.setdefault(label, []).append(index)

    training_indices = []
    validation_indices = []
    test_indices = []
    shuffler = Random(seed)

    for label in sorted(photos_by_label):
        # Shuffle a copy so the dataset's own sample order stays untouched.
        indices = list(photos_by_label[label])
        shuffler.shuffle(indices)

        training_count = int(len(indices) * TRAIN_FRACTION)
        validation_count = int(len(indices) * VALIDATION_FRACTION)

        training_indices += indices[:training_count]
        validation_indices += indices[training_count:training_count + validation_count]
        test_indices += indices[training_count + validation_count:]

    return (
        Subset(training_base, training_indices),
        Subset(evaluation_base, validation_indices),
        Subset(evaluation_base, test_indices),
    )

# wraps each split into a dataloader that hands them out in batches of 32
def make_loaders(batch_size=BATCH_SIZE, root=DATASET_ROOT, seed=SEED,
                 num_workers=NUM_WORKERS):
    """Return (training, validation, test, clean_training) DataLoaders.

    Only the training set is shuffled, so each epoch sees the photos in a new
    order. Validation and test keep a fixed order, which makes their scores
    comparable between runs.

    clean_training holds the same photos as training, read through the
    deterministic transform instead of the augmented one. Scoring it in eval
    mode gives a training accuracy measured exactly the way validation is, so
    the two can be compared. The augmented training accuracy cannot be compared
    to validation directly, because dropout and augmentation both suppress it.
    """
    training_set, validation_set, test_set = split_dataset(root, seed)

    # validation_set.dataset is the ImageFolder carrying validation_transformation.
    clean_training_set = Subset(validation_set.dataset, training_set.indices)

    # Keeping workers alive avoids paying the process spawn cost every epoch.
    persistent = num_workers > 0
    return (
        DataLoader(training_set, batch_size=batch_size, shuffle=True,
                   num_workers=num_workers, persistent_workers=persistent),
        DataLoader(validation_set, batch_size=batch_size, shuffle=False,
                   num_workers=num_workers, persistent_workers=persistent),
        DataLoader(test_set, batch_size=batch_size, shuffle=False,
                   num_workers=num_workers, persistent_workers=persistent),
        # Scored occasionally rather than every epoch, so its workers are not
        # worth keeping alive between uses.
        DataLoader(clean_training_set, batch_size=batch_size, shuffle=False,
                   num_workers=num_workers, persistent_workers=False),
    )
