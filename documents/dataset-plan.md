# Dataset plan (Req 5a / 5b)

Spec for the lost-and-found item classifier dataset. `categories.txt` is the machine-readable category list; this file is for people.

## Categories

29 categories. Folder names are lowercase with underscores and must match the Item `category` field and the post form dropdown exactly. Do not rename after training.

| Category | Photos now | Target | Train (70%) | Val (15%) | Test (15%) | Status |
|---|---|---|---|---|---|---|
| backpack | 100 | 100 | 70 | 15 | 15 | done |
| binder | 47 | 100 | 33 | 7 | 7 | needs more |
| book | 81 | 100 | 57 | 12 | 12 | needs more |
| bracelet | 99 | 100 | 69 | 15 | 15 | needs more |
| calculator | 100 | 100 | 70 | 15 | 15 | done |
| charger | 62 | 100 | 43 | 9 | 10 | needs more |
| earbuds | 86 | 100 | 60 | 13 | 13 | needs more |
| earrings | 100 | 100 | 70 | 15 | 15 | done |
| eyewear | 103 | 100 | 72 | 15 | 16 | done |
| flash_drive | 89 | 100 | 62 | 13 | 14 | needs more |
| gloves | 95 | 100 | 66 | 14 | 15 | needs more |
| hat | 99 | 100 | 69 | 15 | 15 | needs more |
| headphones | 100 | 100 | 70 | 15 | 15 | done |
| jacket | 74 | 100 | 52 | 11 | 11 | needs more |
| keys | 90 | 100 | 63 | 14 | 13 | needs more |
| laptop | 99 | 100 | 69 | 15 | 15 | needs more |
| lunchbox | 80 | 100 | 56 | 12 | 12 | needs more |
| necklace_locket | 133 | 100 | 93 | 20 | 20 | done |
| notebook | 72 | 100 | 50 | 11 | 11 | needs more |
| phone | 100 | 100 | 70 | 15 | 15 | done |
| purse | 100 | 100 | 70 | 15 | 15 | done |
| ring | 100 | 100 | 70 | 15 | 15 | done |
| scarf | 88 | 100 | 62 | 13 | 13 | needs more |
| shoes | 100 | 100 | 70 | 15 | 15 | done |
| sweatshirt | 72 | 100 | 50 | 11 | 11 | needs more |
| umbrella | 97 | 100 | 68 | 15 | 14 | needs more |
| wallet | 99 | 100 | 69 | 15 | 15 | needs more |
| watch | 99 | 100 | 69 | 15 | 15 | needs more |
| water_bottle | 89 | 100 | 62 | 13 | 14 | needs more |
| **Total** | **2653** | **2900** | | | | |

## Where the photos come from

- Free-licensed photos collected by the image classifier code. Every photo's source and license is logged in `attribution.csv`.
- Photos are stored one folder per category: `dataset/<category>/`, using the names in `categories.txt`.

## Photo rules

- One item per photo, item clearly visible, no people, no collages, no extreme close-ups.
- Mix of backgrounds and angles so the model does not learn the background.
- Every photo must pass the image classifier code's automatic photo checks (a zero-shot CLIP check plus extra checks) before it is kept.

## Splits

- 70% train / 15% val / 15% test per category, same categories in every split.
- The split is made at training time from the `dataset/` folder, so the photos are not copied into train/val/test folders ahead of time.
- Keep near-duplicate photos in the same split so test results are not inflated.

## Progress

Categories still under target: binder (47), book (81), bracelet (99), charger (62), earbuds (86), flash_drive (89), gloves (95), hat (99), jacket (74), keys (90), laptop (99), lunchbox (80), notebook (72), scarf (88), sweatshirt (72), umbrella (97), wallet (99), watch (99), water_bottle (89).

Last updated: 2026-11-02
