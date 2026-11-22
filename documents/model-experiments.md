# Experiment Log, Req 5d

One row per finished training run. Per-epoch detail for the most recent run is in
[model-results.md](model-results.md), which is overwritten each time. Test accuracy is
measured separately with `review_errors.py`.

Rows before Nov 19 were reconstructed by hand: `cnn.py` only started appending here
after the overwriting problem was found, and the earlier per-epoch tables were lost to
later runs. Their headline numbers are accurate; per-epoch detail is gone.

| Run started | Architecture | Image | Epochs | Optimizer | Augmentation | Best val | At epoch |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-11-18 (early) | hand-built CNN, 2 conv blocks 6/16, flatten to 5.39M-param FC | 224x224 | 2 of 2 | SGD lr=0.001 momentum=0.9 | resize, hflip, rotate15, jitter 0.2, no normalize | 6.7% | 2 |
| 2026-11-18 (early) | hand-built CNN, 4 conv blocks 32/64/128/256, BN, GAP, dropout 0.3 | 128x128 | 150 of 150 | SGD lr=0.05 momentum=0.9, cosine | rotate15, crop 0.5-1.0, hflip, jitter 0.3, grayscale, erasing 0.25 | 31.0% | — |
| 2026-11-18 16:27 | hand-built CNN, 4 conv blocks 64/128/256/512, BN, GAP, dropout 0.4 | 128x128 | 150 of 150 | SGD lr=0.05 momentum=0.9 nesterov, wd 5e-4, cosine | rotate15, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25 | **49.7%** | 141 |
| 2026-11-18 18:54 | hand-built CNN, 4 conv blocks 64/128/256/512, BN, GAP, dropout 0.4 | 160x160 | 300 of 300 | SGD lr=0.025 momentum=0.9 nesterov, wd 5e-4, cosine | rotate5, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.1 | 46.5% | 166 |
| 2026-11-19 16:41 | ResNet18, ImageNet pretrained, final layer replaced | 224x224 | 41 of 50 (early stop) | AdamW head lr=1e-3 backbone lr=1e-4, wd 1e-4, cosine | crop 0.7-1.0, hflip, jitter 0.2 | **78.8%** | 39 |

## Test accuracy

Measured once per chosen model, on the held-out test split (1,147 photos), with
`review_errors.py`.

| Model | Validation | Test |
| --- | --- | --- |
| Hand-built CNN, best configuration | 49.7% | 51.0% |
| ResNet18 fine-tuned | 78.8% | **81.1%** |

Test came in above validation both times, so the best-of-N epoch selection did not
make validation optimistic in practice.

## What each change bought

| Change | Effect |
| --- | --- |
| Fixing the output layer from 23 to 31 classes | Made training possible at all; it had been crashing |
| Normalize added to the training transform | Removed a train/eval input mismatch |
| 2 conv blocks → 4, BatchNorm, global average pooling | 6.7% → 31% — the first model put 99.7% of its parameters in one FC layer |
| Widening 32/64/128/256 → 64/128/256/512 | Fixed underfitting; moved into overfitting |
| Heavier augmentation, dropout 0.4, weight decay, class weights | 31% → 49.7% |
| 160px, lr 0.025, eased augmentation | 49.7% → 46.5%, a regression; reverted by the backbone switch |
| Dataset refresh: 2,653 photos / 29 classes → 7,533 / 31 | The largest single improvement before the backbone |
| **ResNet18 fine-tuning** | **49.7% → 78.8% validation, 51.0% → 81.1% test** |

## Known ceiling

Error review (`documents/misclassified/`) shows the remaining failures are mostly data,
not model:

- **Mislabeled photos** — e.g. `charger_137.jpg` is a water flosser
- **Non-photo content** — e.g. `umbrella_192.jpg` is a marketing infographic
- **Multi-object frames** — `scarf → jacket` photos usually contain both garments, so
  there is no single correct label
- **Small objects in whole scenes** — Open Images photos scored 34.6% as a source
  against 61.9% for curated ones, on the hand-built model

166 photos are flagged `check` in `newPhotosReview.csv` and have not been reviewed yet.
| 2026-11-19 17:44 | ResNet18, ImageNet pretrained, final layer replaced | 224x224 | 41 of 50 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.0001, cosine annealing | crop scale 0.7-1.0, hflip, jitter 0.2 | **78.8%** | 39 |
| 2026-11-19 18:51 | ResNet18, ImageNet pretrained, final layer replaced, dropout 0.4 | 224x224 | 82 of 120 | AdamW head lr=0.001 backbone lr=3e-05, weight decay 0.001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25 | **77.9%** | 62 |
| 2026-11-19 19:36 | ResNet18, ImageNet pretrained, final layer replaced, dropout 0.4 | 224x224 | 72 of 120 | AdamW head lr=0.001 backbone lr=3e-05, weight decay 0.001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.2 | **77.7%** | 52 |
| 2026-11-19 20:35 | efficientnet_b0, ImageNet pretrained, final layer replaced, dropout 0.3 | 224x224 | 60 of 60 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **83.9%** | 13 |
| 2026-11-19 22:09 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.3 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **77.8%** | 42 |
| 2026-11-19 22:33 | efficientnet_b0, ImageNet pretrained, final layer replaced, dropout 0.3 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **84.5%** | 32 |
| 2026-11-19 23:20 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.5 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.2 | **77.1%** | 38 |
| 2026-11-19 23:45 | efficientnet_b0, ImageNet pretrained, final layer replaced, dropout 0.2 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=3e-05, weight decay 0.001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.2 | **83.1%** | 43 |
| 2026-11-20 00:31 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.4 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=3e-05, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **78.2%** | 36 |
| 2026-11-20 00:57 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.3 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **78.7%** | 36 |
| 2026-11-20 01:22 | efficientnet_b0, ImageNet pretrained, final layer replaced, dropout 0.3 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **84.3%** | 44 |
| 2026-11-20 02:09 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.5 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.2 | **76.8%** | 35 |
| 2026-11-20 02:34 | efficientnet_b0, ImageNet pretrained, final layer replaced, dropout 0.2 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=3e-05, weight decay 0.001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.2 | **82.6%** | 45 |
| 2026-11-20 03:22 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.4 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=3e-05, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **78.7%** | 34 |
| 2026-11-20 03:47 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.3 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **78.6%** | 35 |
| 2026-11-20 04:13 | efficientnet_b0, ImageNet pretrained, final layer replaced, dropout 0.3 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **83.7%** | 40 |
| 2026-11-20 05:00 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.5 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.2 | **77.2%** | 41 |
| 2026-11-20 05:26 | efficientnet_b0, ImageNet pretrained, final layer replaced, dropout 0.2 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=3e-05, weight decay 0.001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.2 | **83.1%** | 26 |
| 2026-11-20 06:13 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.4 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=3e-05, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **77.8%** | 44 |
| 2026-11-20 06:39 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.3 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **77.1%** | 24 |
| 2026-11-20 07:05 | efficientnet_b0, ImageNet pretrained, final layer replaced, dropout 0.3 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **83.8%** | 16 |
| 2026-11-20 07:52 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.5 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.2 | **76.1%** | 29 |
| 2026-11-20 08:17 | efficientnet_b0, ImageNet pretrained, final layer replaced, dropout 0.2 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=3e-05, weight decay 0.001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.2 | **82.7%** | 36 |
| 2026-11-20 09:05 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.4 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=3e-05, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **76.8%** | 38 |
| 2026-11-20 09:31 | resnet18, ImageNet pretrained, final layer replaced, dropout 0.3 | 224x224 | 45 of 45 | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.0001, cosine annealing | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 | **78.1%** | 41 |
