"""Requirement 5e: guess an item's category from its photo.

`predict(image_bytes)` is the only interface the rest of the app uses. The model
loads once, on the first call, and is reused afterwards.

This module deliberately does not import cnn.py or data_pipeline.py. Those are
training scripts that pull in torchvision.datasets and the dataset folder; the
deployed app needs neither. The architecture is rebuilt here from the same three
lines, and test_category_guess.py checks the two stay compatible by loading a
real checkpoint.
"""

import io
import os
import threading
from pathlib import Path

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import models, transforms

from app.categories import CATEGORIES

# ImageFolder numbers its classes by sorted folder name, so sorted(CATEGORIES)
# is exactly the index-to-label mapping the model was trained with. Sorting here
# rather than storing a second list means the two can never drift apart.
LABELS = sorted(CATEGORIES)

# Requirement R3: must match validation_transformation in data_pipeline.py. The
# training transform augments and must never be used here. Global average
# pooling means a size mismatch quietly costs accuracy instead of raising.
IMAGE_SIZE = 224
_PREPROCESS = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# Checkpoints are named per backbone so training one does not overwrite another.
# This is the best model measured so far: ResNet18, validation 78.8% / test
# 81.1%. Point MODEL_WEIGHTS_PATH at a different file to serve a different one.
DEFAULT_WEIGHTS = Path(__file__).resolve().parents[1] / "best_weights_resnet18_base.pt"

# Requirement 5f: a guess at or above this confidence fills the category field.
# Measured on the 1115 validation photos:
#
#   threshold   fills the field   correct when it fills
#       0.50         61.6%               95.3%
#       0.60         54.3%               96.9%   <- chosen
#       0.70         43.8%               98.6%
#       0.80         34.5%               99.2%
#
# 0.60 fills the field for over half of uploads and is right 97% of the time.
# Label smoothing during training flattens confidence, so these numbers are
# lower than an unsmoothed model would produce - do not compare them to
# thresholds from other projects. Raise this if wrong guesses prove annoying;
# the poster can always edit the field (Requirement 11).
#
# This threshold, the accuracy floors Requirement 13 asserts against, and what
# changing the served checkpoint requires are recorded in
# documents/model-decisions.md.
CONFIDENCE_THRESHOLD = 0.60

_model = None
_load_lock = threading.Lock()


def _weights_path():
    return Path(os.getenv("MODEL_WEIGHTS_PATH") or DEFAULT_WEIGHTS)


def _final_layer_classes(state):
    """How many categories a checkpoint predicts, whichever head it was saved with."""
    for key in ("fc.1.weight", "fc.weight", "classifier.1.weight"):
        if key in state:
            return state[key].shape[0]
    raise KeyError("No final linear layer found in the checkpoint.")


def _build(class_count, state):
    """Architecture only, no downloaded weights. Mirrors cnn.build_model().

    The shape is read from the checkpoint's own keys, so every model this
    project has produced still loads:

      fc.weight            ResNet18, bare Linear head (before Nov 19)
      fc.1.weight          ResNet18, Dropout + Linear head
      classifier.1.weight  EfficientNet-B0

    Dropout is inert at inference anyway, since the model runs in eval mode.
    """
    if "classifier.1.weight" in state:
        model = models.efficientnet_b0(weights=None)
        model.classifier[1] = torch.nn.Linear(
            model.classifier[1].in_features, class_count)
        return model

    model = models.resnet18(weights=None)
    if "fc.1.weight" in state:
        model.fc = torch.nn.Sequential(
            torch.nn.Dropout(0.4),
            torch.nn.Linear(model.fc.in_features, class_count),
        )
    else:
        model.fc = torch.nn.Linear(model.fc.in_features, class_count)
    return model


def load_model():
    """Build the network and load our fine-tuned weights. Cached after the first call.

    Requirement R6: nothing is downloaded. The architecture is created empty and
    filled from a weights file we ship, so a cold start never needs the network.
    """
    global _model
    if _model is not None:
        return _model

    with _load_lock:
        if _model is not None:  # another thread won the race
            return _model

        path = _weights_path()
        if not path.exists():
            raise FileNotFoundError(
                f"No model weights at {path}. Train with cnn.py, or set "
                f"MODEL_WEIGHTS_PATH to the checkpoint."
            )

        state = torch.load(path, map_location="cpu")
        trained_classes = _final_layer_classes(state)
        if trained_classes != len(LABELS):
            raise ValueError(
                f"{path.name} predicts {trained_classes} categories but "
                f"app/categories.py lists {len(LABELS)}. Retrain, or restore the "
                f"category list the checkpoint was trained on."
            )

        model = _build(len(LABELS), state)
        model.load_state_dict(state)
        model.eval()  # no dropout, BatchNorm uses its running statistics
        _model = model

    return _model


def predict(image_bytes):
    """Return (category, confidence) for a photo.

    category is one of app.categories.CATEGORIES, and confidence runs 0 to 1.

    Returns (None, 0.0) when the photo cannot be read or the model is
    unavailable. Requirement 5e is explicit that an unreadable image produces no
    category rather than an error, and Requirement 5f is explicit that a failed
    guess must never block posting - so this function does not raise.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as photo:
            tensor = _PREPROCESS(photo.convert("RGB")).unsqueeze(0)

        model = load_model()
        with torch.no_grad():
            probabilities = F.softmax(model(tensor), dim=1)[0]

        confidence, index = probabilities.max(0)
        return LABELS[int(index)], float(confidence)
    except Exception:
        # Deliberately broad: a bad upload, a missing weights file, or a torch
        # failure must all degrade to "no guess" rather than break the post form.
        return None, 0.0


def guess_for_form(image_bytes):
    """Requirement 5f: the category to prefill, or None when unsure.

    Returns (category_or_None, confidence) so the caller can show the confidence
    even when it was too low to fill the field.
    """
    category, confidence = predict(image_bytes)
    if category is None or confidence < CONFIDENCE_THRESHOLD:
        return None, confidence
    return category, confidence
