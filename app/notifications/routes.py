"""A private notification inbox with CSRF-protected open actions."""

from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Notification

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.errorhandler(SQLAlchemyError)
def database_error(_error):
    db.session.rollback()
    return "Notifications are temporarily unavailable. Please try again later.", 503


@notifications_bp.get("/")
@login_required
def inbox():
    pagination = db.paginate(
        db.select(Notification).where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc()),
        per_page=20, max_per_page=20, error_out=False,
    )
    return render_template("notifications/inbox.html", pagination=pagination, form=FlaskForm())


@notifications_bp.post("/<int:notification_id>/open")
@login_required
def open_notification(notification_id):
    notification = db.get_or_404(Notification, notification_id)
    if notification.user_id != current_user.id:
        abort(404)
    form = FlaskForm()
    if not form.validate_on_submit():
        abort(400)

    if notification.message_id is not None:
        message = notification.message
        if current_user.id not in (message.sender_id, message.recipient_id):
            abort(404)
        target = url_for("messages.detail", message_id=message.id)
    else:
        claim = notification.claim
        if current_user.id not in (claim.claimant_id, claim.item.user_id):
            abort(404)
        target = url_for("claims.detail", claim_id=claim.id)

    notification.read = True
    db.session.commit()
    return redirect(target, code=303)
