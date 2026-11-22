from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user
from sqlalchemy import case, func
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Item, User
from app.serializers import serialize_item

profiles_bp = Blueprint("profiles", __name__, url_prefix="/api/profiles")

DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 50

## HELPER FUNCTIONS

def _positive_int_arg(name, default):
    """Retrieve a positive integer from the query parameters."""

    raw_value = request.args.get(name)

    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        return None

    return value if value > 0 else None

def _profile_stats(user_id):
    """Calculate the post statistics of a user."""

    stats_statement = db.select(
        func.count(Item.id).label("total_posts"),
        func.count(case((Item.listing_type == "lost", 1))).label("total_lost"),
        func.count(case((Item.listing_type == "found", 1))).label("total_found"),
        func.count(case((Item.resolved.is_(True), 1))).label("total_resolved")
    ).where(Item.user_id == user_id)

    return db.session.execute(stats_statement).mappings().one()

def _serialize_profile(user, stats, viewer_id=None):
    """Serialize public profile information."""

    return {
        "id": user.id,
        "username": user.display_name,
        "display_name": user.display_name,
        "bio": user.bio,
        "created_at": user.created_at.isoformat() + "Z",
        "is_owner": (viewer_id is not None and user.id == viewer_id),
        "stats": {
            "total_posts": stats["total_posts"],
            "total_lost": stats["total_lost"],
            "total_found": stats["total_found"],
            "total_resolved": stats["total_resolved"]
        }
    }

def _validate_profile_data(data):
    """Validate fields submitted when updating a profile"""

    if not isinstance(data, dict):
        return {}, {"body": "Request must be a JSON object."}

    errors = {}
    cleaned = {}

    # The username is changed on the change-username page, which applies its rules.
    allowed_fields = {"bio"}

    unexpected = set(data) - allowed_fields
    if unexpected:
        errors["body"] = (f"Unexpected fields: {', '.join(sorted(unexpected))}")

    if not data:
        errors["body"] = "At least one field must be provided."

    # Validate bio
    if "bio" in data:
        value = data["bio"]

        if value is None:
            cleaned["bio"] = None
        elif not isinstance(value, str):
            errors["bio"] = "Bio must be a string."
        else:
            value = value.strip()

            if len(value) > 500:
                errors["bio"] = "Bio cannot exceed 500 characters."
            else:
                cleaned["bio"] = value or None
    
    return cleaned, errors

## PROFILES FUNCTIONS

@profiles_bp.get("/<int:user_id>")
def get_profile(user_id):
    """Retrieve a profile by user ID. Return item history and statistics."""

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify(error="User not found."), 404

    # validate pagination paremeters
    page = _positive_int_arg("page", 1) # default page 1
    per_page = _positive_int_arg("per_page", DEFAULT_PER_PAGE)

    if page is None or per_page is None:
        return jsonify(error="page and per_page must be positive integers."), 400

    per_page = min(per_page, MAX_PER_PAGE)

    # Resolved-post history (Req 21) asks for only resolved posts
    resolved_only = request.args.get("resolved")
    if resolved_only not in (None, "true"):
        return jsonify(error="resolved must be true when given."), 400

    # Select totals of posted items, lost items, found items, and resolved items
    stats = _profile_stats(user.id)

    # Post history - Retrieve and paginate the user's posts
    posts_statement = (
        db.select(Item)
        .where(Item.user_id == user.id)
        .order_by(
            Item.date_reported.desc(),
            Item.created_at.desc(),
            Item.id.desc()
        )
    )
    if resolved_only:
        posts_statement = posts_statement.where(Item.resolved.is_(True))

    pagination = db.paginate(
        posts_statement,
        page=page,
        per_page=per_page,
        max_per_page=MAX_PER_PAGE,
        error_out=True
    )

    viewer_id = current_user.id if current_user.is_authenticated else None

    return jsonify(
        profile=_serialize_profile(user, stats, viewer_id),
        posts=[serialize_item(item, viewer_id=viewer_id) for item in pagination.items],
        pagination={
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev
        }
    ), 200

@profiles_bp.patch("/me")
def edit_profile():
    """Update the current user's profile."""

    # User must be logged in
    if not current_user.is_authenticated:
        return jsonify(error="Authentication required."), 401

    if not request.is_json:
        return jsonify(error="Use application/json."), 400

    data = request.get_json(silent=True)
    cleaned, errors = _validate_profile_data(data)
    if errors:
        return jsonify(errors=errors), 400

    user = current_user._get_current_object()

    for field, value in cleaned.items():
        setattr(user, field, value)

    # Commit changes to database
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Profile database error.")
        return jsonify(error="Could not update profile."), 500

    # Return updated profile
    stats = _profile_stats(user.id)

    return jsonify(profile=_serialize_profile(user, stats, viewer_id=user.id)), 200