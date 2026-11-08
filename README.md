# Photo Pipeline

Cleans a photo before FoundIt saves it. It checks that the upload is a real image (Req 6), removes GPS and all other metadata (Req 25), and returns the result as JPEG bytes ready for `save_photo()`.

## Setup

Needs Python 3 with Pillow and pillow-heif (pillow-heif lets it read iPhone HEIC photos).

    pip install pillow pillow-heif

## Usage

    import pipeline
    from errors import PhotoError

    try:
        jpeg_bytes = pipeline.process_photo(uploaded_file)  # file path or file object
    except PhotoError as error:
        print(error.code, error)  # nothing is saved

## Steps

1. **Validate** (`validate.py`) rejects files that are missing, too large, too many pixels, not an image, damaged, or in an unsupported format.
2. **Strip** (`strip_metadata.py`) rotates the photo upright, turns transparent areas white, and rebuilds the image from raw pixels, so GPS, camera info, and every other piece of metadata is removed.
3. **Encode** (`encode_photo.py`) saves the image as a JPEG with no metadata.

## Files

| File | Purpose |
|---|---|
| `pipeline.py` | `process_photo()` runs all three steps |
| `validate.py` | `check()` raises a `PhotoError`; `photo()` returns True/False |
| `strip_metadata.py` | `strip_metadata()`; `has_gps()` checks whether a photo has GPS data |
| `encode_photo.py` | `to_jpeg_bytes()` |
| `errors.py` | `PhotoError` and its error codes |
| `photo_settings.py` | The limits below |

## Settings (`photo_settings.py`)

| Setting | Value |
|---|---|
| `ALLOWED_FORMATS` | JPEG, MPO, PNG, WebP, HEIF/HEIC |
| `MAX_SIZE` | 10 MB |
| `MAX_PIXELS` | 25,000,000 (width × height) |
| `JPEG_QUALITY` | 90 |

## Error codes

| Code | Meaning |
|---|---|
| `FILE_NOT_FOUND` | Missing or unreadable file, or no file was attached |
| `TOO_LARGE` | File is over `MAX_SIZE` |
| `TOO_MANY_PIXELS` | Resolution is over `MAX_PIXELS`; checked from the file header before the image is decoded |
| `NOT_AN_IMAGE` | Not an image, empty, truncated, or damaged |
| `UNSUPPORTED_FORMAT` | A real image in a format that isn't allowed (for example GIF) |

`str(error)` gives a message the user can read, and `error.code` lets the form choose what to show.

## Notes

- An animated file keeps only its first frame.
- Code style is `snake_case`, to match the rest of the team.
