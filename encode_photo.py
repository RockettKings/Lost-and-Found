import io

from photo_settings import JPEG_QUALITY


# Input: a clean RGB PIL image (the output of strip_metadata.strip_metadata).
# Output: the JPEG file as bytes, ready to hand to save_photo. No metadata
#         is written, because none is passed to save().
def to_jpeg_bytes(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)

    return buffer.getvalue()
