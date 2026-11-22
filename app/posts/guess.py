"""Requirement 5f: the endpoint the post form calls to prefill a category.

Registered on the existing posts blueprint from app/posts/__init__.py, so
app/posts/routes.py (Khang's) is not modified. "/category-guess" cannot collide
with the "/<int:post_id>" route, because it is not an integer.
"""

from flask import jsonify, request
from flask_login import current_user

from app.model import guess_for_form
from app.photo_pipeline.pipeline import process_photo
from app.posts.routes import posts_bp


@posts_bp.post("/category-guess")
def category_guess():
    """Return {category, confidence} for an uploaded photo.

    category is null when the photo is unreadable, the model is unavailable, or
    the guess did not clear the confidence threshold. Requirement 5f: a low
    confidence guess leaves the field blank and never blocks posting, so this
    route answers 200 with a null category rather than an error.
    """
    if not current_user.is_authenticated:
        return jsonify(error="Authentication required."), 401

    upload = request.files.get("photo")
    if upload is None or not (getattr(upload, "filename", "") or "").strip():
        return jsonify(category=None, confidence=0.0), 200

    try:
        upload.stream.seek(0)
        # The model sees the same cleaned bytes that get stored: validated,
        # EXIF-stripped, re-encoded. Architecture doc, Flow 1 step 5.
        cleaned_jpeg = process_photo(upload)
    except Exception:
        # A photo the pipeline rejects gets no guess. The real validation error
        # is raised later, by the create/update route, where it belongs.
        return jsonify(category=None, confidence=0.0), 200
    finally:
        try:
            upload.stream.seek(0)
        except (AttributeError, OSError):
            pass

    category, confidence = guess_for_form(cleaned_jpeg)
    return jsonify(category=category, confidence=round(confidence, 4)), 200
