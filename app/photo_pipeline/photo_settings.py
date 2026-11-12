ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP", "HEIF"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB, in bytes
MAX_PIXELS = 25_000_000      # width x height; stops tiny files that decode huge
JPEG_QUALITY = 90            # quality of the JPEG every photo is saved as
