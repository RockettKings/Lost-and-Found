from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy.exc import SQLAlchemyError
from wtforms import TextAreaField
from wtforms.validators import DataRequired, Length

from app.extensions import db
from app.models import Item, Message, Notification, User

messages_bp = Blueprint("messages", __name__, url_prefix="/messages")


@messages_bp.errorhandler(SQLAlchemyError)
def database_error(_error):
    db.session.rollback()
    return "Messages are temporarily unavailable. Please try again later.", 503


class MessageForm(FlaskForm):
    text = TextAreaField("Message", filters=[lambda value: (value or "").strip()],
                         validators=[DataRequired(), Length(max=2000)])


def _save_message(recipient_id, item_id, text):
    message = Message(sender_id=current_user.id, recipient_id=recipient_id,
                      item_id=item_id, text=text)
    db.session.add(message)
    # Both records commit together, including when this send is a reply.
    db.session.add(Notification(user_id=recipient_id, type="message", message=message))
    db.session.commit()
    return redirect(url_for("messages.detail", message_id=message.id))


@messages_bp.route("/new", methods=["GET", "POST"])
@login_required
def compose():
    item = None
    if "item_id" in request.args:
        item_id = request.args.get("item_id", type=int)
        if item_id is None:
            abort(404)
        item = db.get_or_404(Item, item_id)
        recipient = item.user
    else:
        recipient_id = request.args.get("to", type=int)
        if recipient_id is None:
            abort(404)
        recipient = db.get_or_404(User, recipient_id)
    if recipient.id == current_user.id:
        abort(403)

    form = MessageForm()
    if form.validate_on_submit():
        return _save_message(recipient.id, item.id if item else None, form.text.data)
    return render_template("messages/compose.html", recipient=recipient, item=item, form=form)


@messages_bp.get("/")
@login_required
def inbox():
    messages = db.session.scalars(
        db.select(Message).where(Message.recipient_id == current_user.id)
        .order_by(Message.sent_at.desc(), Message.id.desc())
    ).all()
    return render_template("messages/inbox.html", messages=messages)


@messages_bp.route("/<int:message_id>", methods=["GET", "POST"])
@login_required
def detail(message_id):
    message = db.get_or_404(Message, message_id)
    if current_user.id not in (message.sender_id, message.recipient_id):
        abort(404)

    can_reply = current_user.id == message.recipient_id
    form = MessageForm()
    if request.method == "POST":
        if not can_reply:
            abort(403)
        if form.validate_on_submit():
            return _save_message(message.sender_id, message.item_id, form.text.data)
    return render_template("messages/detail.html", message=message, form=form, can_reply=can_reply)
