from flask import Blueprint

# Create posts Blueprint
posts_bp = Blueprint("posts", __name__, url_prefix="/posts")

# Define routes
@posts_bp.route("/<int:post_id>", methods=["GET"])
def get_post(post_id):
    return