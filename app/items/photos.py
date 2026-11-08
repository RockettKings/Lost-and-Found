"""Accept an uploaded image. Saving waits on the photo pipeline."""

from app.storage import delete_photo, save_photo

_MAX_BYTES = 10 * 1024 * 1024


def _is_image(raw):
    if raw.startswith(b"\xff\xd8\xff"):
        return True
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return True
    return len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"


def store_uploaded_photo(upload):
    """Return (photo_key, error, skipped).

    A non-image sets error and stores nothing. A real image is processed and
    saved when pipeline.process_photo is available. Until that function is on
    this branch, skipped is true and no photo key is stored.
    """
    if upload is None or not (getattr(upload, "filename", "") or "").strip():
        return None, None, False

    raw = upload.read()
    if len(raw) > _MAX_BYTES:
        return None, "Image must be 10 MB or smaller.", False
    if not raw or not _is_image(raw):
        return None, "Please choose an image file.", False

    try:
        from pipeline import process_photo
    except ImportError:
        return None, None, True

    try:
        upload.stream.seek(0)
        clean = process_photo(upload)
        return save_photo(clean), None, False
    except ValueError as error:
        message = str(error).strip() or "Please choose an image file."
        return None, message, False


def remove_stored_photo(photo_key):
    if photo_key:
        delete_photo(photo_key)
