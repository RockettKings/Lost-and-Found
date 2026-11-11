from PIL import ExifTags, Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()


# Input: a file path, an uploaded file object, or an open PIL image.
# Output: True if the photo's EXIF data has GPS location entries, otherwise
#         False. Used by the tests to prove GPS is gone after stripping.
def has_gps(image) -> bool:
    if isinstance(image, Image.Image):
        return bool(image.getexif().get_ifd(ExifTags.IFD.GPSInfo))

    with Image.open(image) as img:
        return bool(img.getexif().get_ifd(ExifTags.IFD.GPSInfo))


# Input: a PIL image in any color mode (RGB, RGBA, palette, grayscale, CMYK...).
# Output: a PIL image in RGB mode. Transparent areas become white, because
#         JPEG cannot store transparency.
def flatten_to_rgb(image):
    has_transparency = image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    )

    if has_transparency:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background

    return image.convert("RGB")


# Input: a validated photo as a file path or an uploaded file object.
# Output: a new RGB PIL image with the pixels only, rotated upright. All
#         metadata (GPS, camera info, color profile) is gone because the image
#         is rebuilt from raw pixel bytes. Animated files keep their first frame.
def strip_metadata(image_path):
    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        img = flatten_to_rgb(img)

        return Image.frombytes(img.mode, img.size, img.tobytes())
