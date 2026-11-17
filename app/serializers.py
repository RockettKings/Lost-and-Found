from flask import current_app

from app.storage import get_photo

def _photo_url(item):
    if not item.photo_key:
        return None
    try:
        return get_photo(item.photo_key)
    except Exception:
        current_app.logger.exception("Could not generate a post photo URL.")
        return None

def serialize_item(item, viewer_id=None):
    """Serialize a post without exposing private user information."""
    return {
        "id": item.id,
        "user_id": item.user_id,
        "title": item.title,
        "description": item.description,
        "category": item.category,
        "listing_type": item.listing_type,
        "general_location": item.general_location,
        "date_reported": item.date_reported.isoformat(),
        "created_at": item.created_at.isoformat() + "Z",
        "resolved": bool(item.resolved),
        "photo_url": _photo_url(item),
        "is_owner": bool(viewer_id is not None and item.user_id == viewer_id)
    }