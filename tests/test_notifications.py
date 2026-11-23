"""Reqs 34/44: real events, private inboxes, read state, and direct targets."""

import re
from datetime import datetime, timedelta

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Claim, Item, Message, Notification, User
from tests.conftest import MIGRATIONS

PASSWORD = "notification test password"


@pytest.fixture
def accounts(app):
    with app.app_context():
        password_hash = generate_password_hash(PASSWORD)
        users = [User(email=f"{name}@example.edu", password_hash=password_hash)
                 for name in ("poster", "claimant", "outsider")]
        item = Item(user=users[0], title="Lost blue bag", description="Found at library",
                    category="bags", listing_type="found", general_location="Library",
                    ownership_questions=["What is inside?"])
        db.session.add_all([*users, item])
        db.session.commit()
        return {"poster": users[0].id, "claimant": users[1].id,
                "outsider": users[2].id, "item": item.id}


def sign_in(app, name):
    client = app.test_client()
    response = client.post("/auth/login", data={
        "identifier": f"{name}@example.edu", "password": PASSWORD,
    })
    assert response.status_code == 302
    return client


def submit_claim(app, accounts):
    claimant = sign_in(app, "claimant")
    path = f"/posts/{accounts['item']}/claims/new"
    page = claimant.get(path).get_data(as_text=True)
    version = re.search(r'name="questions_version"[^>]*value="([^"]+)"', page).group(1)
    response = claimant.post(path, data={"questions_version": version, "answers-0": "A red pen"})
    assert response.status_code == 303
    with app.app_context():
        return db.session.scalar(db.select(Claim.id))


def test_claim_submission_notifies_only_poster(app, accounts):
    claim_id = submit_claim(app, accounts)
    with app.app_context():
        notification = db.session.scalars(db.select(Notification)).one()
        assert (notification.user_id, notification.type, notification.claim_id,
                notification.message_id, notification.read) == (
                    accounts["poster"], "claim_submitted", claim_id, None, False)
        assert notification.created_at is not None
    assert b"New claim on Lost blue bag" in sign_in(app, "poster").get("/notifications/").data
    assert b"No notifications yet" in sign_in(app, "outsider").get("/notifications/").data


@pytest.mark.parametrize("decision", ["approved", "denied"])
def test_claim_review_notifies_claimant_once_and_opens_specific_claim(app, accounts, decision):
    claim_id = submit_claim(app, accounts)
    poster = sign_in(app, "poster")
    path = f"/claims/{claim_id}/review"
    assert poster.post(path, data={"decision": decision}).status_code == 303
    assert poster.post(path, data={"decision": decision}).status_code == 409
    with app.app_context():
        notifications = db.session.scalars(db.select(Notification).where(
            Notification.user_id == accounts["claimant"])).all()
        assert len(notifications) == 1
        notification = notifications[0]
        assert notification.claim_id == claim_id and not notification.read
        assert notification.type == f"claim_{decision}"
        notification_id = notification.id
    claimant = sign_in(app, "claimant")
    opened = claimant.post(f"/notifications/{notification_id}/open")
    assert opened.status_code == 303 and opened.location == f"/claims/{claim_id}"
    assert decision.capitalize().encode() in claimant.get(opened.location).data
    with app.app_context():
        assert db.session.get(Notification, notification_id).read is True


def test_new_claim_notification_opens_claim_for_poster(app, accounts):
    claim_id = submit_claim(app, accounts)
    with app.app_context():
        notification_id = db.session.scalar(db.select(Notification.id))
    poster = sign_in(app, "poster")
    opened = poster.post(f"/notifications/{notification_id}/open")
    assert opened.status_code == 303 and opened.location == f"/claims/{claim_id}"
    page = poster.get(opened.location)
    assert b"A red pen" in page.data and b"Approve" in page.data
    assert sign_in(app, "outsider").get(opened.location).status_code == 404


def test_message_and_reply_notify_their_recipients_and_open_message(app, accounts):
    claimant = sign_in(app, "claimant")
    sent = claimant.post(f"/messages/new?item_id={accounts['item']}", data={"text": "Hello"})
    assert sent.status_code == 302
    with app.app_context():
        notification = db.session.scalars(db.select(Notification)).one()
        assert notification.user_id == accounts["poster"]
        assert notification.type == "message" and notification.claim_id is None
        assert notification.message_id is not None and not notification.read
        notification_id = notification.id
    poster = sign_in(app, "poster")
    inbox = poster.get("/notifications/")
    assert b"Unread" in inbox.data and b"New message from" in inbox.data
    # Merely viewing the list does not consume the notification.
    with app.app_context():
        assert db.session.get(Notification, notification_id).read is False
    opened = poster.post(f"/notifications/{notification_id}/open")
    assert opened.status_code == 303 and opened.location == sent.location
    assert b"Hello" in poster.get(opened.location).data
    assert poster.post(opened.location, data={"text": "Hi back"}).status_code == 302
    with app.app_context():
        assert db.session.get(Notification, notification_id).read is True
        reply_notification = db.session.scalars(db.select(Notification).where(
            Notification.user_id == accounts["claimant"])).one()
        assert not reply_notification.read
        assert reply_notification.message.text == "Hi back"
    assert b'class="unread"' not in poster.get("/notifications/").data
    # Reopening is safe and does not create another notification.
    assert poster.post(f"/notifications/{notification_id}/open").location == sent.location
    with app.app_context():
        assert len(db.session.scalars(db.select(Notification)).all()) == 2


def test_foreign_and_anonymous_users_cannot_read_or_mark_notifications(app, accounts):
    sign_in(app, "claimant").post(
        f"/messages/new?to={accounts['poster']}", data={"text": "Private"})
    with app.app_context():
        notification_id = db.session.scalar(db.select(Notification.id))
    outsider = sign_in(app, "outsider")
    assert b"No notifications yet" in outsider.get("/notifications/").data
    assert outsider.post(f"/notifications/{notification_id}/open").status_code == 404
    anonymous = app.test_client()
    assert anonymous.get("/notifications/").status_code == 302
    assert anonymous.post(f"/notifications/{notification_id}/open").status_code == 302
    assert outsider.post("/notifications/99999/open").status_code == 404
    with app.app_context():
        assert db.session.get(Notification, notification_id).read is False


def test_inbox_orders_by_time_then_id_and_paginates(app, accounts):
    base_time = datetime(2026, 11, 1, 12)
    with app.app_context():
        message = Message(sender_id=accounts["claimant"], recipient_id=accounts["poster"], text="Hello")
        notifications = [Notification(user_id=accounts["poster"], type="message", message=message,
                                      created_at=base_time + timedelta(minutes=i)) for i in range(21)]
        # Equal times use the newer id as a stable tie-breaker.
        notifications[-1].created_at = notifications[-2].created_at
        db.session.add_all(notifications)
        db.session.commit()
        expected = [n.id for n in reversed(notifications)]
    poster = sign_in(app, "poster")
    first = poster.get("/notifications/").get_data(as_text=True)
    second = poster.get("/notifications/?page=2").get_data(as_text=True)
    def ids(page):
        return [int(value) for value in re.findall(r'data-notification-id="(\d+)"', page)]

    assert ids(first) == expected[:20]
    assert ids(second) == expected[20:]


def test_open_requires_post_and_csrf(app, accounts):
    sign_in(app, "claimant").post(
        f"/messages/new?to={accounts['poster']}", data={"text": "Hello"})
    with app.app_context():
        notification_id = db.session.scalar(db.select(Notification.id))
    poster = sign_in(app, "poster")
    app.config["WTF_CSRF_ENABLED"] = True
    path = f"/notifications/{notification_id}/open"
    assert poster.get(path).status_code == 405
    assert poster.post(path).status_code == 400
    with app.app_context():
        assert db.session.get(Notification, notification_id).read is False
    page = poster.get("/notifications/").get_data(as_text=True)
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page).group(1)
    assert poster.post(path, data={"csrf_token": token}).status_code == 303


def test_invalid_message_saves_no_notification(app, accounts):
    claimant = sign_in(app, "claimant")
    claimant.post(f"/messages/new?to={accounts['poster']}", data={"text": "   "})
    with app.app_context():
        assert db.session.scalar(db.select(Notification.id)) is None


def test_failed_notification_rolls_back_message_and_can_retry(app, accounts):
    claimant = sign_in(app, "claimant")

    def fail_insert(_mapper, _connection, _notification):
        raise SQLAlchemyError("Simulated notification storage failure")

    event.listen(Notification, "before_insert", fail_insert)
    try:
        response = claimant.post(f"/messages/new?to={accounts['poster']}", data={"text": "Hello"})
        assert response.status_code == 503
    finally:
        event.remove(Notification, "before_insert", fail_insert)
    with app.app_context():
        assert db.session.scalar(db.select(Message.id)) is None
        assert db.session.scalar(db.select(Notification.id)) is None
    assert claimant.post(f"/messages/new?to={accounts['poster']}", data={"text": "Hello"}).status_code == 302
    with app.app_context():
        assert len(db.session.scalars(db.select(Notification)).all()) == 1


def test_deleted_claim_cleans_up_its_notifications(app, accounts):
    claim_id = submit_claim(app, accounts)
    poster = sign_in(app, "poster")
    with app.app_context():
        assert db.session.scalar(db.select(Notification.id)) is not None
        db.session.delete(db.session.get(Claim, claim_id))
        db.session.commit()
        assert db.session.scalar(db.select(Notification.id)) is None
    assert b"No notifications yet" in poster.get("/notifications/").data


def test_failed_notification_rolls_back_claim_decision(app, accounts):
    claim_id = submit_claim(app, accounts)
    poster = sign_in(app, "poster")

    def fail_insert(_mapper, _connection, _notification):
        raise SQLAlchemyError("Simulated notification storage failure")

    event.listen(Notification, "before_insert", fail_insert)
    try:
        response = poster.post(f"/claims/{claim_id}/review", data={"decision": "approved"})
        assert response.status_code == 503
    finally:
        event.remove(Notification, "before_insert", fail_insert)
    with app.app_context():
        assert db.session.get(Claim, claim_id).status == "pending"
        assert len(db.session.scalars(db.select(Notification)).all()) == 1
    assert poster.post(f"/claims/{claim_id}/review", data={"decision": "approved"}).status_code == 303
    with app.app_context():
        assert db.session.get(Claim, claim_id).status == "approved"
        assert len(db.session.scalars(db.select(Notification)).all()) == 2


def test_notification_migration_preserves_existing_messages(app, accounts):
    with app.app_context():
        db.session.remove()
        downgrade(directory=MIGRATIONS, revision="private_messages")
        db.session.execute(text(
            "INSERT INTO messages (sender_id, recipient_id, text, sent_at) "
            "VALUES (:sender, :recipient, 'Existing message', '2026-11-01 12:00:00')"
        ), {"sender": accounts["claimant"], "recipient": accounts["poster"]})
        db.session.commit()
        upgrade(directory=MIGRATIONS)
        message = db.session.scalars(db.select(Message)).one()
        assert message.text == "Existing message"
        assert db.session.scalar(db.select(Notification.id)) is None
        assert db.session.execute(text("PRAGMA foreign_key_check")).all() == []
