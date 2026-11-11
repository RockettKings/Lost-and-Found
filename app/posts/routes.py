from datetime import date

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions import db
from app.posts.photos import remove_stored_photo, store_uploaded_photo
from app.models import Item
from app.storage import photo_url

posts_bp = Blueprint("posts", __name__, url_prefix="/api/posts")

TEXT_LIMITS = {
    "title": 120,
    "description": 2000,
    "category": 80,
    "listing_type": 5,
    "general_location": 200,
}
CREATE_REQUIRED = set(TEXT_LIMITS)
ALLOWED_UPDATE_FIELDS = CREATE_REQUIRED | {"date_reported", "resolved"}


def _discard_photo(photo_key):
    if not photo_key:
        return
    try:
        remove_stored_photo(photo_key)
    except Exception:
        # A failed S3 cleanup should not undo a committed database operation.
        current_app.logger.exception("Could not delete an obsolete post photo.")


def _photo_url(item):
    if not item.photo_key:
        return None
    try:
        return photo_url(item.photo_key)
    except Exception:
        current_app.logger.exception("Could not generate a post photo URL.")
        return None


def _item_to_dict(item):
    """Serialize a post without exposing private user information."""
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "category": item.category,
        "listing_type": item.listing_type,
        "general_location": item.general_location,
        "date_reported": item.date_reported.isoformat(),
        "created_at": item.created_at.isoformat() + "Z",
        "resolved": bool(item.resolved),
        "photo_url": _photo_url(item),
        "is_owner": bool(current_user.is_authenticated and item.user_id == current_user.id),
    }


def _parse_bool(value, field):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError(f"{field} must be true or false.")


def _request_data():
    """Read either a JSON object or multipart/form-data fields."""
    if request.is_json:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return None, {"body": "Request must be a JSON object."}
        return data, {}

    if request.mimetype == "multipart/form-data" or request.mimetype == "application/x-www-form-urlencoded":
        return request.form.to_dict(), {}

    return None, {"body": "Use application/json or multipart/form-data."}


def _validate_item_data(data, partial=False, allow_empty=False):
    if not isinstance(data, dict):
        return {}, {"body": "Request must contain valid post fields."}

    errors = {}
    cleaned = {}

    allowed = ALLOWED_UPDATE_FIELDS if partial else CREATE_REQUIRED | {"date_reported"}
    unexpected = set(data) - allowed
    if unexpected:
        errors["body"] = f"Unexpected fields: {', '.join(sorted(unexpected))}"

    if not partial:
        missing = (CREATE_REQUIRED | {"date_reported"}) - set(data)
        for field in missing:
            errors[field] = "This field is required."

    if partial and not data and not allow_empty:
        errors["body"] = "At least one field or photo operation must be provided."

    for field, max_length in TEXT_LIMITS.items():
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, str):
            errors[field] = "This field must be a string."
            continue
        value = value.strip()
        if not value:
            errors[field] = "This field cannot be empty."
        elif len(value) > max_length:
            errors[field] = f"This field cannot exceed {max_length} characters."
        else:
            cleaned[field] = value

    if "listing_type" in cleaned:
        cleaned["listing_type"] = cleaned["listing_type"].lower()
        if cleaned["listing_type"] not in {"lost", "found"}:
            errors["listing_type"] = "Must be either 'lost' or 'found'."
            cleaned.pop("listing_type", None)

    if "date_reported" in data:
        raw_date = data["date_reported"]
        if not isinstance(raw_date, str):
            errors["date_reported"] = "Date reported must use YYYY-MM-DD."
        else:
            try:
                cleaned["date_reported"] = date.fromisoformat(raw_date.strip())
            except ValueError:
                errors["date_reported"] = "Date reported must use YYYY-MM-DD."

    if "resolved" in data:
        try:
            cleaned["resolved"] = _parse_bool(data["resolved"], "resolved")
        except ValueError as error:
            errors["resolved"] = str(error)

    return cleaned, errors


def _commit():
    try:
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        current_app.logger.exception("Post database integrity error.")
        return False
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Post database error.")
        return False


def _require_login():
    if not current_user.is_authenticated:
        return jsonify(error="Authentication required."), 401
    return None


def _owned_post(post_id):
    item = db.session.get(Item, post_id)
    if item is None:
        return None, (jsonify(error="Post not found."), 404)
    if item.user_id != current_user.id:
        return None, (jsonify(error="You do not own this post."), 403)
    return item, None


@posts_bp.get("/")
def get_posts():
    """List posts. Supports q, category, listing_type, and sort query parameters."""
    statement = db.select(Item)

    query = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    listing_type = (request.args.get("listing_type") or "").strip().lower()
    sort = (request.args.get("sort") or "newest").strip().lower()

    if listing_type and listing_type not in {"lost", "found"}:
        return jsonify(error="listing_type must be 'lost' or 'found'."), 400
    if sort not in {"newest", "oldest"}:
        return jsonify(error="sort must be 'newest' or 'oldest'."), 400

    if query:
        # Escape LIKE metacharacters so user input is treated literally.
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        statement = statement.where(or_(
            Item.title.ilike(pattern, escape="\\"),
            Item.description.ilike(pattern, escape="\\"),
        ))
    if category:
        statement = statement.where(Item.category == category)
    if listing_type:
        statement = statement.where(Item.listing_type == listing_type)

    order = Item.date_reported.desc() if sort == "newest" else Item.date_reported.asc()
    statement = statement.order_by(order, Item.created_at.desc())

    items = db.session.execute(statement).scalars().all()
    return jsonify(posts=[_item_to_dict(item) for item in items]), 200


@posts_bp.get("/<int:post_id>")
def get_post(post_id):
    item = db.session.get(Item, post_id)
    if item is None:
        return jsonify(error="Post not found."), 404
    return jsonify(post=_item_to_dict(item)), 200


@posts_bp.post("/")
def create_post():
    auth_error = _require_login()
    if auth_error:
        return auth_error

    data, request_errors = _request_data()
    if request_errors:
        return jsonify(errors=request_errors), 400

    cleaned, errors = _validate_item_data(data)
    if errors:
        return jsonify(errors=errors), 400

    photo_key, photo_error = store_uploaded_photo(request.files.get("photo"))
    if photo_error:
        return jsonify(errors={"photo": photo_error}), 400

    item = Item(user_id=current_user.id, photo_key=photo_key, **cleaned)
    db.session.add(item)

    if not _commit():
        _discard_photo(photo_key)
        return jsonify(error="Could not create the post."), 500

    return jsonify(post=_item_to_dict(item)), 201


@posts_bp.patch("/<int:post_id>")
def update_post(post_id):
    auth_error = _require_login()
    if auth_error:
        return auth_error

    item, error_response = _owned_post(post_id)
    if error_response:
        return error_response

    data, request_errors = _request_data()
    if request_errors:
        return jsonify(errors=request_errors), 400

    upload = request.files.get("photo")
    remove_photo = False
    if "remove_photo" in data:
        try:
            remove_photo = _parse_bool(data.pop("remove_photo"), "remove_photo")
        except ValueError as error:
            return jsonify(errors={"remove_photo": str(error)}), 400

    has_upload = bool(upload and (upload.filename or "").strip())
    if has_upload and remove_photo:
        return jsonify(errors={"photo": "Choose a replacement photo or remove the existing photo, not both."}), 400
    cleaned, errors = _validate_item_data(data, partial=True, allow_empty=has_upload or remove_photo)
    if errors:
        return jsonify(errors=errors), 400
    if not cleaned and not has_upload and not remove_photo:
        return jsonify(errors={"body": "No changes were supplied."}), 400

    new_photo_key = None
    if has_upload:
        new_photo_key, photo_error = store_uploaded_photo(upload)
        if photo_error:
            return jsonify(errors={"photo": photo_error}), 400

    previous_photo_key = item.photo_key
    for field, value in cleaned.items():
        setattr(item, field, value)

    if new_photo_key:
        item.photo_key = new_photo_key
    elif remove_photo:
        item.photo_key = None

    if not _commit():
        _discard_photo(new_photo_key)
        return jsonify(error="Could not update the post."), 500

    if (new_photo_key or remove_photo) and previous_photo_key:
        _discard_photo(previous_photo_key)

    return jsonify(post=_item_to_dict(item)), 200


@posts_bp.delete("/<int:post_id>")
def delete_post(post_id):
    auth_error = _require_login()
    if auth_error:
        return auth_error

    item, error_response = _owned_post(post_id)
    if error_response:
        return error_response

    photo_key = item.photo_key
    db.session.delete(item)
    if not _commit():
        return jsonify(error="Could not delete the post."), 500

    _discard_photo(photo_key)
    return "", 204
