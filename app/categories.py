"""Requirement 5a: the labeled categories the image model is trained on.

These are the folder names under documents/dataset, so predict() returns one of
these exact strings. Requirement 11 checks a submitted category against this
set, which keeps the poster's choice and the model's guess on one vocabulary.
"""

CATEGORIES = {
    "backpack",
    "binder",
    "book",
    "bracelet",
    "calculator",
    "charger",
    "earbuds",
    "earrings",
    "eyewear",
    "flash_drive",
    "gloves",
    "hat",
    "headphones",
    "jacket",
    "keys",
    "laptop",
    "lunchbox",
    "necklace_locket",
    "notebook",
    "phone",
    "purse",
    "ring",
    "scarf",
    "shoes",
    "sweatshirt",
    "umbrella",
    "wallet",
    "watch",
    "water_bottle",
}
