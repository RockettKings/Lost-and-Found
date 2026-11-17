"""HTML page routes only. Profile data comes from the JSON API in app.profiles.routes."""

from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import User

profile_pages_bp = Blueprint("profile_pages", __name__, url_prefix="/profiles")


@profile_pages_bp.get("/me")
@login_required
def mine():
    return redirect(url_for("profile_pages.view", user_id=current_user.id))


@profile_pages_bp.get("/<int:user_id>")
def view(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    is_owner = current_user.is_authenticated and current_user.id == user.id
    # The API never returns emails, so the owner's own email comes from the session.
    return render_template("profiles/view.html", user_id=user.id,
                           email=current_user.email if is_owner else None)


@profile_pages_bp.get("/me/edit")
@login_required
def edit():
    return render_template("profiles/edit.html", user=current_user)
