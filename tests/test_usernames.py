"""Unique usernames at sign-up."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import User
from tests.test_auth import login, register
from tests.test_posts import _create_item, _create_user, _login_viewer


def _users(test_db):
    return test_db.session.execute(test_db.select(User)).scalars().all()


# USERNAMES
# ---------

def test_register_saves_username_and_shows_it(client, test_db):
    response = register(client, username="Nick_H")
    assert response.status_code == 302
    assert [user.username for user in _users(test_db)] == ["Nick_H"]
    assert b"@Nick_H" in client.get("/").data


@pytest.mark.parametrize("taken,attempt", [
    ("Nick_H", "Nick_H"),
    ("Nick_H", "nick_h"),
    ("Nick_H", "NICK_H"),
])
def test_username_cannot_be_copied_in_any_case(client, test_db, taken, attempt):
    register(client, email="first@example.edu", username=taken)
    client.post("/auth/logout")

    response = register(client, email="second@example.edu", username=attempt)

    assert response.status_code == 200
    assert b"That username is already taken." in response.data
    assert len(_users(test_db)) == 1


@pytest.mark.parametrize("username,message", [
    ("ab", b"3\xe2\x80\x9320 characters"),
    ("a" * 21, b"3\xe2\x80\x9320 characters"),
    ("has space", b"letters, numbers, and underscores"),
    ("bad<script>", b"letters, numbers, and underscores"),
    ("", b"This field is required"),
    ("Admin", b"reserved"),
    ("MODERATOR", b"reserved"),
    ("user12", b"reserved"),
    ("User7", b"reserved"),
])
def test_register_rejects_bad_usernames(client, test_db, username, message):
    response = register(client, username=username)
    assert response.status_code == 200
    assert message in response.data
    assert _users(test_db) == []


def test_database_blocks_duplicate_usernames_ignoring_case(test_db):
    """Even code that skips the form can't create a look-alike username."""
    test_db.session.add(User(email="a@example.edu", username="Sam", password_hash="x"))
    test_db.session.commit()
    test_db.session.add(User(email="b@example.edu", username="sAM", password_hash="x"))
    with pytest.raises(IntegrityError):
        test_db.session.commit()
    test_db.session.rollback()


def test_post_shows_author_username_not_email(client, test_db):
    user_id = _create_user(test_db, "student@example.edu")
    post_id = _create_item(test_db, user_id)
    _login_viewer(client, test_db)

    post = client.get(f"/api/posts/{post_id}").get_json()["post"]

    assert post["author"] == "student"
    assert "student@example.edu" not in str(post)


def test_migration_backfills_unique_usernames(app, test_db):
    from flask_migrate import downgrade, upgrade
    from tests.conftest import MIGRATIONS

    downgrade(directory=MIGRATIONS, revision="0003")
    for user_id, email in [(1, "sam@a.edu"), (2, "SAM@b.edu"), (3, "x@c.edu"), (4, "j.doe+1@d.edu")]:
        test_db.session.execute(test_db.text(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES (:i, :e, 'x', '2026-01-01')"),
            {"i": user_id, "e": email})
    test_db.session.execute(test_db.text(
        "INSERT INTO items (user_id, title, description, category, listing_type, general_location, "
        "date_reported, created_at) VALUES (1, 't', 'd', 'c', 'lost', 'l', '2026-01-01', '2026-01-01')"))
    test_db.session.commit()

    upgrade(directory=MIGRATIONS)

    names = [u.username for u in sorted(_users(test_db), key=lambda u: u.id)]
    # Public names must not reveal anything from the private email address.
    assert names == ["user1", "user2", "user3", "user4"]


# LOG IN WITH USERNAME
# --------------------

def _signup_and_logout(client, username="Nick_H", email="nick@example.edu"):
    register(client, email=email, username=username)
    client.post("/auth/logout")


@pytest.mark.parametrize("identifier", ["Nick_H", "nick_h", "  NICK_H ", "nick@example.edu", "NICK@example.edu"])
def test_login_with_username_or_email(client, test_db, identifier):
    _signup_and_logout(client)

    response = login(client, email=identifier)

    assert response.status_code == 302
    assert b"@Nick_H" in client.get("/").data


@pytest.mark.parametrize("identifier", ["Nick_H", "nobody", "nick@example.edu", "nobody@example.edu"])
def test_login_failures_all_look_the_same(client, test_db, identifier):
    _signup_and_logout(client)

    response = login(client, email=identifier, password="wrong password!!")

    assert response.status_code == 200
    assert b"Invalid email, username, or password." in response.data


def test_password_cannot_equal_username(client, test_db):
    response = register(client, username="correct_horse_battery", password="correct_horse_battery")
    assert b"Password cannot be your username." in response.data


# CHANGE USERNAME
# ---------------

def test_change_username_requires_login(client):
    response = client.get("/auth/username")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_change_username(client, test_db):
    register(client, email="nick@example.edu", username="Nick_H")
    assert b'value="Nick_H"' in client.get("/auth/username").data

    response = client.post("/auth/username", data={"username": "NickTheFinder"})

    assert response.status_code == 302
    assert [u.username for u in _users(test_db)] == ["NickTheFinder"]
    assert b"@NickTheFinder" in client.get("/").data

    client.post("/auth/logout")
    assert login(client, email="NickTheFinder").status_code == 302


def test_change_case_of_own_username_is_allowed(client, test_db):
    register(client, email="nick@example.edu", username="nick_h")
    assert client.post("/auth/username", data={"username": "Nick_H"}).status_code == 302
    assert [u.username for u in _users(test_db)] == ["Nick_H"]


@pytest.mark.parametrize("attempt,message", [
    ("taken_name", b"already taken"),
    ("TAKEN_NAME", b"already taken"),
    ("admin", b"reserved"),
    ("user3", b"reserved"),
    ("a b", b"letters, numbers, and underscores"),
])
def test_change_username_rejects_taken_and_invalid(client, test_db, attempt, message):
    _signup_and_logout(client, username="taken_name", email="first@example.edu")
    register(client, email="second@example.edu", username="Second")

    response = client.post("/auth/username", data={"username": attempt})

    assert response.status_code == 200
    assert message in response.data
    assert sorted(u.username for u in _users(test_db)) == ["Second", "taken_name"]


def test_old_username_is_freed_after_change(client, test_db):
    register(client, email="first@example.edu", username="Original")
    client.post("/auth/username", data={"username": "Renamed"})
    client.post("/auth/logout")

    response = register(client, email="second@example.edu", username="original")

    assert response.status_code == 302
