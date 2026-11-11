from . import validate
from . import strip_metadata
from . import encode_photo


# Input: a photo as a file path or an uploaded file object.
# Output: the cleaned photo as JPEG bytes (no GPS or other metadata, rotation
#         applied), ready to hand to save_photo.
# Raises: errors.PhotoError (a ValueError) if the photo is rejected. Print
#         the error to see what went wrong and what to do next.
def process_photo(image):
    validate.check(image)

    clean = strip_metadata.strip_metadata(image)

    return encode_photo.to_jpeg_bytes(clean)
