from flask import Blueprint

# Create profiles Blueprint
profiles_bp = Blueprint("profiles", __name__, url_prefix="/profiles")

# Define routes
@profiles_bp.route("/<int:profile_id>", methods=["GET"])
def get_profile(profile_id):
    return