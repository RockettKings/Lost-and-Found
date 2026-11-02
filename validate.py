import os

from PIL import Image
from pillow_heif import register_heif_opener
from photo_settings import ALLOWED_FORMATS
from photo_settings import MAX_PIXELS
from photo_settings import MAX_SIZE
import errors

register_heif_opener()


# Input: a file path or an uploaded file object.
# Output: True if the file is MAX_SIZE bytes or smaller, otherwise False.
#         Reads the real byte size without decoding the image.
# Raises: OSError if a path does not exist or cannot be read.
def max_size(image) -> bool:
    if isinstance(image, (str, os.PathLike)):
        size = os.path.getsize(image)
    else:
        image.seek(0, os.SEEK_END)
        size = image.tell()
        image.seek(0)

    return size <= MAX_SIZE


# Input: a file path or an uploaded file object.
# Output: a fully loaded PIL image if the file is a readable image, otherwise
#         None (not an image, empty, truncated, or damaged in any way).
# Raises: errors.PhotoError (TOO_MANY_PIXELS) if width x height is over
#         MAX_PIXELS. This is checked from the file header, before any pixels
#         are decoded, so a tiny file that expands into a huge image is stopped.
def path(image_path):
    try:
        image = Image.open(image_path)  # reads the header only
    except Image.DecompressionBombError:
        raise errors.too_many_pixels()
    except Exception:  # any decoder can fail in its own way on hostile files
        return None

    width, height = image.size
    if width * height > MAX_PIXELS:
        image.close()
        raise errors.too_many_pixels()

    try:
        image.load()  # full decode, so truncated files fail here
    except Exception:
        return None

    return image


# Input: a loaded PIL image (the output of path()).
# Output: True if its format is in ALLOWED_FORMATS, otherwise False.
def format(image) -> bool:
    return image.format in ALLOWED_FORMATS


# Input: a file path or an uploaded file object.
# Output: nothing if the photo is acceptable.
# Raises: errors.PhotoError with a message saying what is wrong and what to do
#         next (FILE_NOT_FOUND, TOO_LARGE, TOO_MANY_PIXELS, NOT_AN_IMAGE or
#         UNSUPPORTED_FORMAT).
def check(image_path):
    try:
        small_enough = max_size(image_path)
    except OSError:  # missing or unreadable file
        raise errors.file_not_found()

    if not small_enough:
        raise errors.too_large()

    image = path(image_path)

    if image is None:
        raise errors.not_an_image()

    if not format(image):
        raise errors.unsupported_format(image.format)


# Input: a file path or an uploaded file object.
# Output: True if the photo is acceptable, otherwise False. Use check() when
#         you need to know why it was rejected.
def photo(image_path) -> bool:
    try:
        check(image_path)
    except errors.PhotoError:
        return False

    return True
