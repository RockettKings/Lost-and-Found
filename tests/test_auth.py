"""Part D: account sign-up, login, logout, and session security."""

import re

import pytest
from flask_migrate import upgrade

from app import create_app
from app.extensions import db
from app.models import User
from tests.conftest import MIGRATIONS

GOOD_PASSWORD = "correct horse battery"


def register(client, email="student@example.edu", password=GOOD_PASSWORD, confirm=None):
    return client.post("/auth/register", data={
        "email": email, "password": password,
        "confirm": password if confirm is None else confirm,
    })


def login(client, email="student@example.edu", password=GOOD_PASSWORD, next_url=None):
    url = "/auth/login" + (f"?next={next_url}" if next_url else "")
    return client.post(url, data={"email": email, "password": password})


def test_register_stores_hash_not_password(client, app):
    response = register(client, email="  Student@Example.EDU ")
    assert response.status_code == 302
    with app.app_context():
        user = db.session.execute(db.select(User)).scalar_one()
        assert user.email == "student@example.edu"
        assert GOOD_PASSWORD not in user.password_hash
        assert user.password_hash.startswith("scrypt:")
        assert user.check_password(GOOD_PASSWORD)


def test_register_logs_user_in(client):
    register(client)
    assert b"Logged in as student@example.edu" in client.get("/").data


@pytest.mark.parametrize("email,password,confirm,message", [
    ("not-an-email", GOOD_PASSWORD, None, b"Invalid email"),
    ("a@example.edu", "short", None, b"10\xe2\x80\x93128 characters"),
    ("a@example.edu", "x" * 129, None, b"10\xe2\x80\x93128 characters"),
    ("a@example.edu", "password123", None, b"too common"),
    ("a@example.edu", GOOD_PASSWORD, "different password", b"must match"),
])
def test_register_rejects_bad_input(client, app, email, password, confirm, message):
    response = register(client, email=email, password=password, confirm=confirm)
    assert response.status_code == 200
    assert message in response.data
    with app.app_context():
        assert db.session.execute(db.select(User)).first() is None


def test_duplicate_registration_is_rejected(client, app):
    register(client)
    client.post("/auth/logout")
    response = register(client, email="STUDENT@example.edu")
    assert b"already exists" in response.data
    with app.app_context():
        assert len(db.session.execute(db.select(User)).all()) == 1


def test_login_and_logout(client):
    register(client)
    client.post("/auth/logout")
    assert b"Log in" in client.get("/").data

    response = login(client)
    assert response.status_code == 302
    assert b"Logged in as" in client.get("/").data

    client.post("/auth/logout")
    assert b"Logged in as" not in client.get("/").data


def test_logout_requires_post(client):
    register(client)
    assert client.get("/auth/logout").status_code == 405
    assert b"Logged in as" in client.get("/").data


def test_wrong_email_and_wrong_password_look_identical(client):
    register(client)
    client.post("/auth/logout")
    wrong_password = login(client, password="wrong password!!")
    wrong_email = login(client, email="nobody@example.edu")
    assert wrong_password.status_code == wrong_email.status_code == 200
    assert b"Invalid email or password." in wrong_password.data
    assert b"Invalid email or password." in wrong_email.data
    assert b"Logged in as" not in client.get("/").data


@pytest.mark.parametrize("next_url,expected", [
    ("/profiles/1", "/profiles/1"),
    ("https://evil.example.com", "/"),
    ("//evil.example.com", "/"),
    ("/\\evil.example.com", "/"),
])
def test_login_redirect_stays_on_site(client, next_url, expected):
    register(client)
    client.post("/auth/logout")
    response = login(client, next_url=next_url)
    assert response.headers["Location"] == expected


def test_session_cookie_flags(client):
    response = register(client)
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_csrf_is_enforced(tmp_path):
    app = create_app({
        "TESTING": True, "APP_ENV": "testing", "SECRET_KEY": "csrf-test",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'csrf.sqlite3'}",
    })
    with app.app_context():
        upgrade(directory=MIGRATIONS)
    client = app.test_client()

    # A forged form with no token is refused, and no account is created.
    response = register(client)
    assert response.status_code == 400

    # The real form includes a token and works.
    page = client.get("/auth/register").data.decode()
    token = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', page).group(1)
    response = client.post("/auth/register", data={
        "csrf_token": token, "email": "student@example.edu",
        "password": GOOD_PASSWORD, "confirm": GOOD_PASSWORD,
    })
    assert response.status_code == 302
    with app.app_context():
        assert db.session.execute(db.select(User)).scalar_one().email == "student@example.edu"
        db.session.remove()
        db.engine.dispose()
