import pytest
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Item, Message, User

PASSWORD = "private messaging test password"


@pytest.fixture
def participants(app):
    password_hash = generate_password_hash(PASSWORD)
    users = [User(email=f"{name}@example.edu", password_hash=password_hash)
             for name in ("sender", "recipient", "outsider")]
    post = Item(user=users[1], title="Backpack", description="Blue backpack",
                category="bags", listing_type="found", general_location="Library")
    with app.app_context():
        db.session.add_all([*users, post])
        db.session.commit()
        return (*[user.id for user in users], post.id)


def sign_in(client, name):
    response = client.post("/auth/login", data={
        "identifier": f"{name}@example.edu", "password": PASSWORD,
    })
    assert response.status_code == 302


@pytest.mark.parametrize("entry_point", ["profile", "post"])
def test_message_from_entry_point_and_immediate_reply(app, participants, entry_point):
    sender_id, recipient_id, _outsider_id, post_id = participants
    sender = app.test_client()
    recipient = app.test_client()
    sign_in(sender, "sender")
    sign_in(recipient, "recipient")

    if entry_point == "post":
        page, compose, item_id = f"/posts/{post_id}", f"/messages/new?item_id={post_id}", post_id
    else:
        page, compose, item_id = f"/profiles/{recipient_id}", f"/messages/new?to={recipient_id}", None

    assert compose.encode() in sender.get(page).data
    assert sender.get(compose).status_code == 200
    sent = sender.post(compose, data={"text": "Is this yours?", "sender_id": recipient_id})
    assert sent.status_code == 302
    assert sent.location.encode() in recipient.get("/messages/").data
    assert b"Is this yours?" in recipient.get(sent.location).data
    assert b"Reply" in recipient.get(sent.location).data

    reply = recipient.post(sent.location, data={"text": "Yes, thank you!"})
    assert reply.status_code == 302
    assert b"Yes, thank you!" in sender.get(reply.location).data
    with app.app_context():
        messages = db.session.scalars(db.select(Message).order_by(Message.id)).all()
        assert [(m.sender_id, m.recipient_id, m.item_id, m.text) for m in messages] == [
            (sender_id, recipient_id, item_id, "Is this yours?"),
            (recipient_id, sender_id, item_id, "Yes, thank you!"),
        ]
        assert all(message.sent_at is not None for message in messages)


def test_message_rejects_outsiders_and_blank_body(app, participants):
    _, recipient_id, _, _ = participants
    sender = app.test_client()
    outsider = app.test_client()
    anonymous = app.test_client()
    sign_in(sender, "sender")
    sign_in(outsider, "outsider")
    compose = f"/messages/new?to={recipient_id}"

    invalid = sender.post(compose, data={"text": "  "})
    assert b"This field is required." in invalid.data
    with app.app_context():
        assert db.session.scalars(db.select(Message)).first() is None

    sent = sender.post(compose, data={"text": "Private message"})
    assert sent.status_code == 302
    assert sent.location.encode() not in outsider.get("/messages/").data
    assert outsider.get(sent.location).status_code == 404
    assert outsider.post(sent.location, data={"text": "Unauthorized reply"}).status_code == 404
    assert anonymous.get(sent.location).status_code == 302
    with app.app_context():
        assert len(db.session.scalars(db.select(Message)).all()) == 1
