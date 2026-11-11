"""HTML page routes only. All post data operations live in app.posts.routes."""

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Item

pages_bp = Blueprint("pages", __name__, url_prefix="/posts")


@pages_bp.get("/new")
@login_required
def create_post():
    return render_template("posts/form.html", mode="create", post_id=None)


@pages_bp.get("/<int:post_id>")
def detail(post_id):
    # Check existence so a bad URL gets the normal 404 page.
    if db.session.get(Item, post_id) is None:
        abort(404)
    return render_template("posts/detail.html", post_id=post_id)


@pages_bp.get("/<int:post_id>/edit")
@login_required
def edit_post(post_id):
    item = db.session.get(Item, post_id)
    if item is None:
        abort(404)
    if item.user_id != current_user.id:
        abort(403)
    return render_template("posts/form.html", mode="edit", post_id=post_id)
