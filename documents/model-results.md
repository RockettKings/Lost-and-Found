# Model Results, Req 5d

Written by `cnn.py`. **The next run overwrites this file** - copy or rename
it before starting another experiment if you want to keep these numbers.

## Settings

| Setting | Value |
| --- | --- |
| run started | 2026-11-20 09:57 |
| architecture | efficientnet_b0, ImageNet pretrained, final layer replaced, dropout 0.3 |
| parameters | 4,047,259 |
| categories | 31 |
| image size | 224x224 |
| split | 5271 train / 1115 val / 1147 test |
| batch size | 32 |
| epochs | 45 |
| optimizer | AdamW head lr=0.001 backbone lr=0.0001, weight decay 0.0001, cosine annealing |
| loss | CrossEntropyLoss, class weighted, label smoothing 0.1 |
| augmentation | rotate10, crop 0.5-1.0, hflip, jitter 0.3, grayscale 0.1, erasing 0.25, mixup alpha 0.0 |
| clean train scored | every 10 epochs and on the last |
| early stopping | disabled, full schedule |
| split seed | 581 |
| training seed | 1004 |
| device | mps |

## Per epoch

| Epoch | Train loss | Train acc | Val loss | Val acc | Clean train acc | Gap | Best so far |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2.068 | 55.9% | 1.393 | 75.6% |  |  | yes |
| 2 | 1.282 | 80.3% | 1.297 | 78.1% |  |  | yes |
| 3 | 1.106 | 87.1% | 1.243 | 81.1% |  |  | yes |
| 4 | 0.997 | 91.4% | 1.236 | 80.7% |  |  |  |
| 5 | 0.929 | 94.2% | 1.230 | 82.5% |  |  | yes |
| 6 | 0.890 | 95.5% | 1.218 | 81.4% |  |  |  |
| 7 | 0.841 | 97.2% | 1.224 | 81.4% |  |  |  |
| 8 | 0.828 | 97.6% | 1.218 | 82.4% |  |  |  |
| 9 | 0.815 | 98.0% | 1.205 | 83.0% |  |  | yes |
| 10 | 0.804 | 98.3% | 1.220 | 83.0% | 99.9% | +16.9 pts |  |
| 11 | 0.795 | 98.3% | 1.208 | 81.9% |  |  |  |
| 12 | 0.781 | 99.1% | 1.201 | 82.3% |  |  |  |
| 13 | 0.774 | 99.1% | 1.199 | 82.6% |  |  |  |
| 14 | 0.771 | 99.1% | 1.190 | 82.9% |  |  |  |
| 15 | 0.760 | 99.3% | 1.183 | 82.8% |  |  |  |
| 16 | 0.757 | 99.4% | 1.190 | 82.9% |  |  |  |
| 17 | 0.755 | 99.5% | 1.194 | 82.5% |  |  |  |
| 18 | 0.752 | 99.5% | 1.181 | 83.0% |  |  |  |
| 19 | 0.749 | 99.3% | 1.187 | 82.5% |  |  |  |
| 20 | 0.745 | 99.4% | 1.186 | 82.8% | 99.9% | +17.1 pts |  |
| 21 | 0.739 | 99.6% | 1.186 | 82.1% |  |  |  |
| 22 | 0.736 | 99.6% | 1.176 | 82.3% |  |  |  |
| 23 | 0.733 | 99.7% | 1.185 | 81.9% |  |  |  |
| 24 | 0.729 | 99.7% | 1.174 | 82.5% |  |  |  |
| 25 | 0.734 | 99.5% | 1.173 | 82.4% |  |  |  |
| 26 | 0.726 | 99.8% | 1.166 | 82.6% |  |  |  |
| 27 | 0.725 | 99.8% | 1.168 | 83.0% |  |  |  |
| 28 | 0.724 | 99.8% | 1.175 | 82.5% |  |  |  |

Best validation accuracy **83.0%**, reached at epoch 9.

## Reading the two training accuracies

**Train acc** is measured while training: dropout on, augmentation applied.
It is handicapped on purpose and is not comparable to validation accuracy.

**Clean train acc** is the same photos scored the way validation is scored:
eval mode, no dropout, no augmentation. Only this number is comparable, and
**Gap** is clean train minus validation - the real overfitting gap.

- Clean train low (say under 80%) means the model still cannot fit its own
  training data. That is underfitting: add capacity, cut regularization, or
  raise resolution.
- Clean train high with a large gap means it fits training and fails to
  generalize. That is overfitting: add regularization or more photos.

## Worst confusions at the best epoch

Validation set, `true -> predicted`, from the Req 5d confusion matrix.

| Count | True label | Predicted as |
| --- | --- | --- |
| 5 | scarf | jacket |
| 5 | jacket | sweatshirt |
| 4 | sweatshirt | jacket |
| 4 | notebook | textbook |
| 4 | keys | earbuds |
| 4 | eyeglasses | sunglasses |
| 3 | sunglasses | shoes |
| 3 | purse | wallet |
| 3 | gloves | shoes |
| 3 | bracelet | necklace |
| 2 | watch | ring |
| 2 | sweatshirt | umbrella |
| 2 | purse | backpack |
| 2 | phone | laptop |
| 2 | notebook | wallet |

Look-alike pairs dominating this table points at resolution or label
noise. Unrelated pairs dominating points at capacity.
