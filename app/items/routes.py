"""HTML pages for browsing and managing posts. /posts stays a JSON API."""

from flask import Blueprint, abort, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.items.forms import ItemForm, PostActionForm
from app.items.photos import remove_stored_photo, store_uploaded_photo
from app.models import Item
from app.storage import photo_url

items_bp = Blueprint("items", __name__, url_prefix="/items")


def _commit():
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not save a post.")
        return False
    return True


def _owned_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        abort(404)
    if not current_user.is_authenticated or item.user_id != current_user.id:
        abort(403)
    return item


def _photo_src(item):
    if not item.photo_key:
        return None
    try:
        return photo_url(item.photo_key)
    except Exception:
        current_app.logger.exception("Could not build a photo link.")
        return None


def _apply_form(item, form):
    item.title = form.title.data
    item.description = form.description.data
    item.category = form.category.data
    item.listing_type = form.listing_type.data
    item.general_location = form.general_location.data
    item.date_reported = form.date_reported.data


@items_bp.route("/<int:item_id>")
def detail(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        abort(404)
    owner = current_user.is_authenticated and item.user_id == current_user.id
    return render_template(
        "items/detail.html",
        item=item,
        owner=owner,
        photo_src=_photo_src(item),
        action_form=PostActionForm(),
    )


@items_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_item():
    form = ItemForm()
    if form.validate_on_submit():
        photo_key, error, skipped = store_uploaded_photo(form.photo.data)
        if error:
            form.photo.errors.append(error)
        else:
            item = Item(user_id=current_user.id, photo_key=photo_key)
            _apply_form(item, form)
            db.session.add(item)
            if _commit():
                if skipped:
                    flash(
                        "Post saved. The photo will be attached once image processing is available.",
                        "info",
                    )
                return redirect(url_for("items.detail", item_id=item.id))
            if photo_key:
                _discard_photo(photo_key)
            flash("Could not save the post.", "error")
    return render_template("items/form.html", form=form, heading="New post", submit_label="Create post")


@items_bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    item = _owned_item(item_id)
    form = ItemForm(obj=item)
    if form.validate_on_submit():
        photo_key, error, skipped = store_uploaded_photo(form.photo.data)
        if error:
            form.photo.errors.append(error)
        else:
            previous_key = item.photo_key
            _apply_form(item, form)
            if photo_key:
                item.photo_key = photo_key
            if _commit():
                if photo_key and previous_key and previous_key != photo_key:
                    _discard_photo(previous_key)
                if skipped:
                    flash(
                        "Post saved. The photo will be attached once image processing is available.",
                        "info",
                    )
                return redirect(url_for("items.detail", item_id=item.id))
            if photo_key:
                _discard_photo(photo_key)
            flash("Could not save the post.", "error")
    return render_template("items/form.html", form=form, heading="Edit post", submit_label="Save changes")


@items_bp.route("/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    item = _owned_item(item_id)
    if not PostActionForm().validate_on_submit():
        abort(400)
    photo_key = item.photo_key
    db.session.delete(item)
    if not _commit():
        flash("Could not delete the post.", "error")
        return redirect(url_for("items.detail", item_id=item_id))
    _discard_photo(photo_key)
    flash("Post deleted.", "info")
    return redirect(url_for("index"))


@items_bp.route("/<int:item_id>/resolve", methods=["POST"])
@login_required
def resolve_item(item_id):
    item = _owned_item(item_id)
    if not PostActionForm().validate_on_submit():
        abort(400)
    item.resolved = True
    if _commit():
        flash("Post marked resolved.", "success")
    else:
        flash("Could not update the post.", "error")
    return redirect(url_for("items.detail", item_id=item.id))


def _discard_photo(photo_key):
    try:
        remove_stored_photo(photo_key)
    except Exception:
        current_app.logger.exception("Could not delete a stored photo.")
