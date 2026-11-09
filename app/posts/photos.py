"""Bridge between uploaded files, E's image pipeline, and S3 storage."""

from app.storage import delete_photo, save_photo


def store_uploaded_photo(upload):
    """Return (new_photo_key, error_message).

    An empty file input means that no replacement was requested. The image
    pipeline validates the actual file format, size, dimensions, and strips
    metadata before the resulting JPEG is stored.
    """
    if upload is None or not (getattr(upload, "filename", "") or "").strip():
        return None, None

    try:
        upload.stream.seek(0)
        from app.photo_pipeline.pipeline import process_photo

        cleaned_jpeg = process_photo(upload)
        return save_photo(cleaned_jpeg), None
    except ValueError as error:
        return None, str(error) or "Please choose a valid image."
    finally:
        try:
            upload.stream.seek(0)
        except (AttributeError, OSError):
            pass


def remove_stored_photo(photo_key):
    if photo_key:
        delete_photo(photo_key)
