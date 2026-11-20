# Overnight Training Sweep, Req 5d

Written by `overnight.py`. **21 run(s) finished**, 11.2 h of training, updated 2026-11-20 09:57.

Every run shares one train/validation/test split (`data_pipeline.SEED`), so these numbers are directly comparable and the checkpoints can be ensembled. Only the training seed and the configuration change.

| Rank | Config | Backbone | Seed | Dropout | MixUp | Backbone LR | WD | Best val | At epoch | Min | Checkpoint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | B-effnet-light | efficientnet_b0 | 1000 | 0.3 | 0.0 | 0.0001 | 0.0001 | **84.5%** | 32 | 45 | kept |
| 2 | B-effnet-light | efficientnet_b0 | 1001 | 0.3 | 0.0 | 0.0001 | 0.0001 | **84.3%** | 44 | 45 | kept |
| 3 | B-effnet-light | efficientnet_b0 | 1003 | 0.3 | 0.0 | 0.0001 | 0.0001 | **83.8%** | 16 | 45 | kept |
| 4 | B-effnet-light | efficientnet_b0 | 1002 | 0.3 | 0.0 | 0.0001 | 0.0001 | **83.7%** | 40 | 45 | kept |
| 5 | D-effnet-mixup | efficientnet_b0 | 1000 | 0.2 | 0.2 | 3e-05 | 0.001 | **83.1%** | 43 | 46 | kept |
| 6 | D-effnet-mixup | efficientnet_b0 | 1002 | 0.2 | 0.2 | 3e-05 | 0.001 | **83.1%** | 26 | 46 | kept |
| 7 | D-effnet-mixup | efficientnet_b0 | 1003 | 0.2 | 0.2 | 3e-05 | 0.001 | **82.7%** | 36 | 46 | kept |
| 8 | D-effnet-mixup | efficientnet_b0 | 1001 | 0.2 | 0.2 | 3e-05 | 0.001 | **82.6%** | 45 | 45 | kept |
| 9 | A-resnet-light | resnet18 | 1001 | 0.3 | 0.0 | 0.0001 | 0.0001 | **78.7%** | 36 | 24 | kept |
| 10 | E-resnet-frozen | resnet18 | 1001 | 0.4 | 0.0 | 3e-05 | 0.0001 | **78.7%** | 34 | 24 | kept |
| 11 | A-resnet-light | resnet18 | 1002 | 0.3 | 0.0 | 0.0001 | 0.0001 | **78.6%** | 35 | 24 | pruned |
| 12 | E-resnet-frozen | resnet18 | 1000 | 0.4 | 0.0 | 3e-05 | 0.0001 | **78.2%** | 36 | 24 | pruned |
| 13 | A-resnet-light | resnet18 | 1004 | 0.3 | 0.0 | 0.0001 | 0.0001 | **78.1%** | 41 | 24 | pruned |
| 14 | E-resnet-frozen | resnet18 | 1002 | 0.4 | 0.0 | 3e-05 | 0.0001 | **77.8%** | 44 | 24 | pruned |
| 15 | A-resnet-light | resnet18 | 1000 | 0.3 | 0.0 | 0.0001 | 0.0001 | **77.8%** | 42 | 24 | pruned |
| 16 | C-resnet-heavy | resnet18 | 1002 | 0.5 | 0.2 | 0.0001 | 0.001 | **77.2%** | 41 | 24 | pruned |
| 17 | C-resnet-heavy | resnet18 | 1000 | 0.5 | 0.2 | 0.0001 | 0.001 | **77.1%** | 38 | 24 | pruned |
| 18 | A-resnet-light | resnet18 | 1003 | 0.3 | 0.0 | 0.0001 | 0.0001 | **77.1%** | 24 | 24 | pruned |
| 19 | C-resnet-heavy | resnet18 | 1001 | 0.5 | 0.2 | 0.0001 | 0.001 | **76.8%** | 35 | 24 | pruned |
| 20 | E-resnet-frozen | resnet18 | 1003 | 0.4 | 0.0 | 3e-05 | 0.0001 | **76.8%** | 38 | 24 | pruned |
| 21 | C-resnet-heavy | resnet18 | 1003 | 0.5 | 0.2 | 0.0001 | 0.001 | **76.1%** | 29 | 24 | pruned |

## Best per configuration

| Config | Runs | Best val | Mean val |
| --- | --- | --- | --- |
| A-resnet-light | 5 | 78.7% | 78.1% |
| B-effnet-light | 4 | 84.5% | 84.1% |
| C-resnet-heavy | 4 | 77.2% | 76.8% |
| D-effnet-mixup | 4 | 83.1% | 82.9% |
| E-resnet-frozen | 4 | 78.7% | 77.9% |

## Ensemble

Greedily selected from 13 kept checkpoints (3 chosen), with horizontal-flip test-time augmentation. Rescored after every run.

Chosen: `run06_B-effnet-light_seed1001`, `best_weights_resnet18_base`, `run01_B-effnet-light_seed1000`

| | Validation | Test |
| --- | --- | --- |
| Best single model (+TTA) | 84.6% | - |
| **ENSEMBLE (+TTA)** | **85.5%** | **86.0%** |


Best single model so far: **84.5%** (B-effnet-light, seed 1000).

Per-epoch detail for each run is in `overnight_results/`. The ensemble
above is rescored automatically after every run, so there is nothing
left to run by hand.
