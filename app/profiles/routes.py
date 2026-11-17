"""Requirement 10: profiles show a user's name and posts, never their email to others."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Item, User
from app.profiles.forms import ProfileForm

profiles_bp = Blueprint("profiles", __name__, url_prefix="/profiles")


def public_profile(user):
    # Only these fields reach the template, so another user's email cannot leak.
    return {"id": user.id, "name": user.public_name, "bio": user.bio, "joined": user.created_at}


@profiles_bp.get("/me")
@login_required
def mine():
    return redirect(url_for("profiles.view", user_id=current_user.id))


@profiles_bp.get("/<int:user_id>")
def view(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    is_owner = current_user.is_authenticated and current_user.id == user.id
    pagination = db.paginate(db.select(Item).where(Item.user_id == user.id)
                            .order_by(Item.date_reported.desc(), Item.id.desc()),
                            per_page=20, max_per_page=20, error_out=False)
    return render_template("profiles/view.html", profile=public_profile(user), is_owner=is_owner,
                           email=user.email if is_owner else None, pagination=pagination)


@profiles_bp.route("/me/edit", methods=["GET", "POST"])
@login_required
def edit():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.display_name = form.display_name.data or None
        current_user.bio = form.bio.data or None
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.display_name.errors.append("That display name is already taken.")
        else:
            flash("Profile updated.", "success")
            return redirect(url_for("profiles.mine"), code=303)
    return render_template("profiles/edit.html", form=form), (400 if request.method == "POST" else 200)
