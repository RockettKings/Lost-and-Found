# Sample photos for Req 13

93 photos, three per category across all 31 categories, for Lydia's Req 13
tests: "category guess on held-out photos."

**Every photo here comes from the test split, never the training or validation
split.** They were selected by reading `data_pipeline.split_dataset()` itself,
so they are the same held-out photos that produced the test accuracy in
[documents/model-decisions.md](../../documents/model-decisions.md). The model
has never seen them.

## Layout

```
tests/sample_photos/<category>/<filename>.jpg
```

The folder name is the label - the same strings as `app.categories.CATEGORIES`,
so a test can walk the tree and compare directly against `predict()`:

```python
from pathlib import Path
from app import model

SAMPLES = Path(__file__).parent / "sample_photos"

for photo in sorted(SAMPLES.rglob("*.jpg")):
    expected = photo.parent.name
    guess, confidence = model.predict(photo.read_bytes())
```

The accuracy floor, the confidence threshold, and what a Req 13 run should
assert are in [documents/model-decisions.md](../../documents/model-decisions.md).
Assert against those numbers rather than hard-coding new ones here.

Tests that need these photos should skip, not fail, when
`app.model.DEFAULT_WEIGHTS` is absent - the same way
`tests/test_category_guess.py` already does - so a teammate who has not pulled
the checkpoint still gets a green run.

## How they were prepared

Each photo was re-encoded down to a 512-pixel long side at JPEG quality 85,
which keeps the whole fixture at about 3 MB instead of about 30 MB. Aspect ratio
is preserved, and `app/model.py` resizes to 224x224 itself, so this does not
change what the model sees in any meaningful way. Re-encoding also dropped all
EXIF metadata from the originals.

Regenerating the set with different photos would invalidate the measured numbers
in `documents/model-decisions.md`, so treat the fixture as fixed and re-measure
if it ever changes.

## Licensing

The photos come from Wikimedia Commons, Open Images, Amazon Berkeley Objects,
Flickr, and several museum and public-domain collections, under CC0, public
domain, CC BY, and CC BY-SA licenses. `ATTRIBUTION.csv` lists the title, license,
artist, and source page for every file in this directory, as those licenses
require. The files are resized derivatives of the originals, as noted above.
