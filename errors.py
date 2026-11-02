from photo_settings import MAX_PIXELS, MAX_SIZE


# Input: a code (short label) and a message (what happened and what to do next).
# Output: an exception, a kind of ValueError, raised when a photo is rejected.
#         str(error) is the message; error.code lets the calling code decide
#         what to show (for example, map a code to a form message).
class PhotoError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# Input: nothing.
# Output: a PhotoError (code FILE_NOT_FOUND) for a missing or unreadable file.
def file_not_found():
    return PhotoError(
        "FILE_NOT_FOUND",
        "The photo could not be read. If you passed a file path, check that the "
        "file exists. If it is an upload, check that the form field is named "
        "correctly and the file was attached.",
    )


# Input: nothing (the limit comes from MAX_SIZE).
# Output: a PhotoError (code TOO_LARGE) for a file over the size limit.
def too_large():
    mb = MAX_SIZE // (1024 * 1024)
    return PhotoError(
        "TOO_LARGE",
        f"The photo is larger than {mb} MB. Nothing was saved. "
        "Ask the user to choose a smaller photo.",
    )


# Input: nothing (the limit comes from MAX_PIXELS).
# Output: a PhotoError (code TOO_MANY_PIXELS) for a photo whose resolution is too high.
def too_many_pixels():
    megapixels = MAX_PIXELS // 1_000_000
    return PhotoError(
        "TOO_MANY_PIXELS",
        f"The photo's resolution is too high (over {megapixels} megapixels). "
        "Nothing was saved. Ask the user to choose a smaller photo.",
    )


# Input: nothing.
# Output: a PhotoError (code NOT_AN_IMAGE) for a file that is not a readable image.
def not_an_image():
    return PhotoError(
        "NOT_AN_IMAGE",
        "That file is not a photo. It may be a video or another kind of file, or "
        "the photo may be empty or damaged. Nothing was saved. Ask the user to "
        "choose a different photo.",
    )


# Input: found = the image format name that was rejected, such as "GIF".
# Output: a PhotoError (code UNSUPPORTED_FORMAT) naming that format.
def unsupported_format(found):
    return PhotoError(
        "UNSUPPORTED_FORMAT",
        f"Photos in {found} format are not supported. Use JPEG, PNG, WebP or "
        "HEIC. Nothing was saved. Ask the user to choose a different photo.",
    )
