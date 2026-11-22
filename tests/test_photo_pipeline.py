import io
import os

import pytest
from PIL import Image

from app.photo_pipeline import errors
from app.photo_pipeline import pipeline
from app.photo_pipeline import validate


def make_bytes(fmt, mode="RGB", size=(200, 200)):
    buffer = io.BytesIO()
    Image.new(mode, size, "red").save(buffer, fmt)
    return buffer.getvalue()


def decode(jpeg_bytes):
    return Image.open(io.BytesIO(jpeg_bytes))


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


# ---- good photos pass ------------------------------------------------------

@pytest.mark.parametrize("fmt, name", [("JPEG", "a.jpg"), ("PNG", "a.png"), ("WEBP", "a.webp")])
def test_valid_photos_pass(tmp_path, fmt, name):
    path = write(tmp_path, name, make_bytes(fmt))
    assert validate.photo(path) is True
    assert decode(pipeline.process_photo(path)).size == (200, 200)


def test_uploaded_file_object_passes():
    upload = io.BytesIO(make_bytes("JPEG"))          # what Flask hands us
    assert validate.photo(upload) is True
    assert decode(pipeline.process_photo(upload)).size == (200, 200)


# ---- bad files are rejected with the right message -------------------------

jpeg = make_bytes("JPEG")

BAD_FILES = {
    "text_renamed.jpg": (b"this is not an image", "NOT_AN_IMAGE"),
    "empty.jpg": (b"", "NOT_AN_IMAGE"),
    "truncated.jpg": (jpeg[: len(jpeg) // 2], "NOT_AN_IMAGE"),
    "animation.gif": (make_bytes("GIF"), "UNSUPPORTED_FORMAT"),
    "picture.bmp": (make_bytes("BMP"), "UNSUPPORTED_FORMAT"),
}


@pytest.mark.parametrize("name", BAD_FILES)
def test_bad_files_are_rejected(tmp_path, name):
    data, code = BAD_FILES[name]
    path = write(tmp_path, name, data)

    assert validate.photo(path) is False
    with pytest.raises(errors.PhotoError) as caught:
        pipeline.process_photo(path)

    assert caught.value.code == code
    assert str(caught.value)          # there is a message to print


def test_file_over_max_size_is_rejected(tmp_path, monkeypatch):
    path = write(tmp_path, "big.jpg", jpeg)
    monkeypatch.setattr(validate, "MAX_SIZE", len(jpeg) - 1)

    with pytest.raises(errors.PhotoError) as caught:
        pipeline.process_photo(path)
    assert caught.value.code == "TOO_LARGE"


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(errors.PhotoError) as caught:
        pipeline.process_photo(str(tmp_path / "nope.jpg"))
    assert caught.value.code == "FILE_NOT_FOUND"


# ---- nothing is saved on a reject ------------------------------------------

def test_rejected_upload_saves_nothing(tmp_path):
    path = write(tmp_path, "text_renamed.jpg", b"not an image")
    before = sorted(os.listdir(tmp_path))

    with pytest.raises(errors.PhotoError):
        pipeline.process_photo(path)

    assert sorted(os.listdir(tmp_path)) == before


# ---- output: JPEG bytes with no GPS ----------------------------------------

import pillow_heif
from app.photo_pipeline import strip_metadata


def exif_with_gps(orientation=None):
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (38.0, 57.0, 0.0), "W", (95.0, 15.0, 0.0)
    exif[0x8825] = gps
    return exif


def test_gps_is_removed_and_output_is_jpeg(tmp_path):
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), "red").save(buffer, "JPEG", exif=exif_with_gps())
    path = write(tmp_path, "gps.jpg", buffer.getvalue())
    assert strip_metadata.has_gps(path) is True          # the test photo really has GPS

    out = pipeline.process_photo(path)

    assert isinstance(out, bytes)
    assert decode(out).format == "JPEG"
    assert strip_metadata.has_gps(io.BytesIO(out)) is False
    assert len(decode(out).getexif()) == 0


def test_rotated_phone_photo_comes_out_upright(tmp_path):
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), "red").save(buffer, "JPEG", exif=exif_with_gps(orientation=6))
    path = write(tmp_path, "rotated.jpg", buffer.getvalue())

    assert decode(pipeline.process_photo(path)).size == (20, 40)   # width and height swapped


def test_transparent_png_becomes_white_background(tmp_path):
    buffer = io.BytesIO()
    Image.new("RGBA", (20, 20), (255, 0, 0, 0)).save(buffer, "PNG")   # fully transparent
    path = write(tmp_path, "clear.png", buffer.getvalue())

    pixel = decode(pipeline.process_photo(path)).convert("RGB").getpixel((10, 10))
    assert all(channel >= 250 for channel in pixel)


@pytest.mark.parametrize("mode, fmt, name", [("P", "PNG", "p.png"), ("L", "JPEG", "g.jpg"), ("CMYK", "JPEG", "c.jpg")])
def test_other_color_modes_come_out_rgb_jpeg(tmp_path, mode, fmt, name):
    buffer = io.BytesIO()
    Image.new(mode, (20, 20)).save(buffer, fmt)
    path = write(tmp_path, name, buffer.getvalue())

    out = decode(pipeline.process_photo(path))
    assert out.format == "JPEG" and out.mode == "RGB"


def test_heic_with_gps_is_cleaned(tmp_path):
    path = str(tmp_path / "gps.heic")
    pillow_heif.from_pillow(Image.new("RGB", (40, 20), "blue")).save(path, exif=exif_with_gps().tobytes())
    assert strip_metadata.has_gps(path) is True

    out = pipeline.process_photo(path)
    assert decode(out).format == "JPEG"
    assert strip_metadata.has_gps(io.BytesIO(out)) is False


# ---- security: pixel limit and corrupt files --------------------------------

import random

from app.photo_pipeline.photo_settings import MAX_PIXELS


def blank_png(width, height):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, "PNG")
    return buffer.getvalue()


def test_photo_at_the_pixel_limit_is_accepted(tmp_path):
    path = write(tmp_path, "limit.png", blank_png(5000, 5000))      # exactly 25,000,000
    assert 5000 * 5000 == MAX_PIXELS
    assert decode(pipeline.process_photo(path)).size == (5000, 5000)


def test_photo_over_the_pixel_limit_is_rejected(tmp_path):
    path = write(tmp_path, "over.png", blank_png(5001, 5000))       # a small file, over the limit
    with pytest.raises(errors.PhotoError) as caught:
        pipeline.process_photo(path)
    assert caught.value.code == "TOO_MANY_PIXELS"


def test_huge_dimensions_are_rejected_not_crashed(tmp_path):
    path = write(tmp_path, "huge.png", blank_png(14000, 14000))     # past Pillow's own bomb limit
    with pytest.raises(errors.PhotoError) as caught:
        pipeline.process_photo(path)
    assert caught.value.code == "TOO_MANY_PIXELS"


def test_pixel_limit_is_checked_before_decoding(tmp_path, monkeypatch):
    from PIL import ImageFile

    def fail(*args, **kwargs):
        raise AssertionError("pixels were decoded before the size was checked")

    path = write(tmp_path, "over.png", blank_png(6000, 6000))
    monkeypatch.setattr(ImageFile.ImageFile, "load", fail)

    with pytest.raises(errors.PhotoError) as caught:
        pipeline.process_photo(path)
    assert caught.value.code == "TOO_MANY_PIXELS"


# A 74-byte PNG with a damaged chunk after the image data. Pillow raises
# SyntaxError for this one, which used to escape as a crash.
CORRUPT_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000080000000808020000004b6d29dc"
    "0000000b4944415478da63fccf801d30310c290900cd41010fbb7836aa0000000049454e44ae425982"
)


def test_corrupt_png_is_rejected_not_crashed(tmp_path):
    path = write(tmp_path, "corrupt.png", CORRUPT_PNG)
    with pytest.raises(errors.PhotoError) as caught:
        pipeline.process_photo(path)
    assert caught.value.code == "NOT_AN_IMAGE"


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_random_corruption_never_crashes(fmt):
    """Every damaged file must be accepted or rejected with a PhotoError, never another exception."""
    rng = random.Random(5)
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), "red").save(buffer, fmt)
    original = buffer.getvalue()

    for _ in range(150):
        data = bytearray(original)
        for _ in range(rng.randint(1, 10)):
            data[rng.randrange(len(data))] = rng.randrange(256)
        if rng.random() < 0.3:
            data = data[: rng.randrange(1, len(data))]
        try:
            pipeline.process_photo(io.BytesIO(bytes(data)))
        except errors.PhotoError:
            pass
