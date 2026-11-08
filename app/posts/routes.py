from flask import Blueprint, jsonify, request, current_app
from flask_login import current_user
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions import db
from app.models import Item

# Create posts Blueprint
posts_bp = Blueprint('posts', __name__, url_prefix='/posts')

# Define routes
def _item_to_dict(item):
    """Converts Item attributes to a dictionary for JSON"""
    return {
        'id': item.id,
        'title': item.title,
        'description': item.description,
        'category': item.category,
        'listing_type': item.listing_type,
        'general_location': item.general_location,
        'date_reported': item.date_reported.isoformat(),
        'created_at': item.created_at.isoformat() + "Z"
    }

def _validate_item_data(data, partial=False):
    """Validate and clean the fields submitted when adding/updating a post"""

    # if data is not a dictionary, it cannot be a JSON object
    if not isinstance(data, dict):
        return None, {'body': "Request must be a JSON object."}

    # character limits for the given fields
    field_limits = {
        'title': 120,
        'description': 2000,
        'category': 80,
        'listing_type': 5,
        'general_location': 200
    }

    errors = {}
    cleaned_data = {}

    unexpected = set(data) - set(field_limits)
    if unexpected:
        errors['body'] = f"Unexpected fields: {', '.join(sorted(unexpected))}"

    # If updating, check that the data contains at least one field
    if partial and not data:
        errors['body'] = "At least one field must be provided."

    # For each field defined in field_limits, validate/clean in the data
    for field, max_length in field_limits.items():
        # Check that the field exists in the data
        if field not in data:
            # If adding, all fields are required
            if not partial:
                errors[field] = "This field is required."

            continue

        value = data[field]

        # Check that all values are string type
        if not isinstance(value, str):
            errors[field] = "This field must be a string."
            continue

        value = value.strip()

        # Check values for errors
        if not value:
            errors[field] = "This field cannot be empty."
        elif len(value) > max_length:
            errors[field] = f'this field cannot exceed {max_length} characters.'
        else:
            cleaned_data[field] = value

    # check for valid listing type
    if 'listing_type' in cleaned_data:
        cleaned_data['listing_type'] = cleaned_data["listing_type"].lower()

        if cleaned_data['listing_type'] not in ('lost', 'found'):
            errors['listing_type'] = "Must be either 'lost' or 'found'."
            cleaned_data.pop('listing_type')

    return cleaned_data, errors

@posts_bp.route('/<int:post_id>', methods=['GET'])
def get_post(post_id):
    """Retrieve a post by its ID from the database"""
    item = db.session.get(Item, post_id)

    # Post not found in the database
    if item is None:
        return jsonify(error="Post not found."), 404

    return jsonify(_item_to_dict(item)), 200

@posts_bp.route('/', methods=['GET'])
def get_posts():
    """Retrieve all posts, optionally filtered by category or listing type"""

    statement = db.select(Item)

    # Optionally, if a category filter is applied, retrieve only posts matching that category
    category = request.args.get('category', '').strip()
    if category:
        statement = statement.where(Item.category == category)

    # Invalid listing type error
    listing_type = request.args.get('listing_type', '').strip().lower()
    if listing_type:
        if listing_type not in ('lost', 'found'):
            return jsonify(error="listing_type must be 'lost' or 'found'."), 400

        statement = statement.where(Item.listing_type == listing_type)

    statement = statement.order_by(Item.created_at.desc())
    items = db.session.execute(statement).scalars().all()
    return jsonify(posts=[_item_to_dict(item) for item in items]), 200

@posts_bp.route('/', methods=['POST'])
def create_post():
    """Create a new post and add it to the database"""

    # A new post must be created by a logged-in user
    if not current_user.is_authenticated:
        return jsonify(error="Authentication required."), 401

    data = request.get_json(silent=True)

    cleaned_data, errors = _validate_item_data(data)

    if errors:
        return jsonify(errors=errors), 400

    # Create a new item with the current user's ID and the cleaned data
    item = Item(user_id=current_user.id, **cleaned_data)
    db.session.add(item)

    # Attempt to commit changes to the database. If it fails, perform a rollback
    try:
        db.session.commit()

    # Check that database integrity constraints are not violated
    except IntegrityError:
        db.session.rollback()
        current_app.logger.exception("Database integrity error occurred while creating post.")
        return jsonify(error="Could not create listing."), 400

    # Check for other database-related errors
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Database error occurred while creating post.")
        return jsonify(error="A database error occurred."), 500

    return jsonify(post=_item_to_dict(item)), 201

@posts_bp.route('/<int:post_id>', methods=['PATCH'])
def update_post(post_id):
    """Edit an existing post"""

    # Check that the user is logged in
    if not current_user.is_authenticated:
        return jsonify(error="Authentication required."), 401

    item = db.session.get(Item, post_id)
    if item is None:
        return jsonify(error="Post not found."), 404

    # Only the owner of the post can edit it
    if item.user_id != current_user.id:
        return jsonify(error="You do not own this post."), 403

    # Retrieve the submitted JSON, validate it
    data = request.get_json(silent=True)
    cleaned_data, errors = _validate_item_data(data, partial=True)

    if errors:
        return jsonify(errors=errors), 400

    # Update only the relevant fields
    for field, value in cleaned_data.items():
        setattr(item, field, value)

    # Attempt to save changes to the database
    try:
        db.session.commit()

    # Check that database integrity constraints are not violated
    except IntegrityError:
        db.session.rollback()
        current_app.logger.exception("Database integrity error occurred while updating post.")
        return jsonify(error="Could not update listing."), 400

    # Check for other database-related errors
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Database error occurred while updating post.")
        return jsonify(error="A database error occurred."), 500

    return jsonify(post=_item_to_dict(item)), 200

@posts_bp.route('/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    """Delete an existing post"""

    # Check that the user is logged in
    if not current_user.is_authenticated:
        return jsonify(error="Authentication required."), 401

    # Retrieve the item to be deleted from the database
    item = db.session.get(Item, post_id)
    if item is None:
        return jsonify(error="Post not found."), 404

    # Check that the user has permission to delete the post
    if item.user_id != current_user.id:
        return jsonify(error="You do not own this post."), 403

    # Attempt to delete the entry and commit the changes in the database
    try:
        db.session.delete(item)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        current_app.logger.exception("Database integrity error occurred while deleting post.")
        return jsonify(error="Could not delete listing because it is referenced by another record."), 409

    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Database error occurred while deleting post.")
        return jsonify(error="A database error occurred."), 500

    return '', 204