"""Rate limiting on sensitive routes, and auto-closing posts after 60 days."""

from datetime import timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import Item, utc_now
from app.posts.expiry import close_expired_posts
from tests.test_auth import register
from tests.test_posts import _create_item, _create_user, _login, _valid_post_data


@pytest.fixture
def app(tmp_path):
    """Same as conftest's app, but with rate limiting on (fresh counters per test)."""
    from flask_migrate import upgrade
    from tests.conftest import MIGRATIONS

    application = create_app({
        "TESTING": True, "APP_ENV": "testing", "SECRET_KEY": "limit-tests-only",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.sqlite3'}",
        "S3_BUCKET": "test-bucket", "WTF_CSRF_ENABLED": False,
        "RATELIMIT_ENABLED": True,
    })
    with application.app_context():
        upgrade(directory=MIGRATIONS)
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def limited_client(client):
    return client


# RATE LIMITING
# -------------

def test_login_is_limited_after_five_attempts(limited_client):
    for _ in range(5):
        response = limited_client.post("/auth/login", data={"identifier": "x@example.edu", "password": "wrong"})
        assert response.status_code == 200

    response = limited_client.post("/auth/login", data={"identifier": "x@example.edu", "password": "wrong"})

    assert response.status_code == 429
    assert b"Too many requests" in response.data
    assert b"Log in" in response.data  # Rendered inside the normal site layout.


def test_viewing_the_login_page_is_not_limited(limited_client):
    for _ in range(10):
        assert limited_client.get("/auth/login").status_code == 200


def test_register_is_limited(limited_client):
    statuses = [register(limited_client, password="short").status_code for _ in range(6)]
    assert statuses == [200] * 5 + [429]


def test_post_creation_is_limited_with_json_error(limited_client, test_db):
    _create_user(test_db, "student@example.edu")
    _login(limited_client, "student@example.edu")

    statuses = [limited_client.post("/api/posts/", data=_valid_post_data()).status_code
                for _ in range(11)]

    assert statuses == [201] * 10 + [429]
    response = limited_client.post("/api/posts/", data=_valid_post_data())
    assert response.get_json() == {"error": "Too many requests. Please wait a minute and try again."}


def test_production_limits_each_client_ip_separately(tmp_path):
    """Behind Render's proxy, limits must follow the real client IP, not the proxy's."""
    from flask_migrate import upgrade
    from tests.conftest import MIGRATIONS

    app = create_app({
        "APP_ENV": "production", "SECRET_KEY": "x" * 40,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'prod.sqlite3'}",
        "WTF_CSRF_ENABLED": False, "RATELIMIT_ENABLED": True,
    })
    with app.app_context():
        upgrade(directory=MIGRATIONS)
    client = app.test_client()

    def attempt(ip):
        return client.post("/auth/login", data={"identifier": "x@example.edu", "password": "wrong"},
                           headers={"X-Forwarded-For": ip}).status_code

    try:
        assert [attempt("203.0.113.1") for _ in range(6)][-1] == 429
        assert attempt("203.0.113.2") == 200  # A different visitor is unaffected.
    finally:
        with app.app_context():
            db.engine.dispose()


# AUTO-CLOSING
# ------------

def _age_post(test_db, post_id, days):
    item = test_db.session.get(Item, post_id)
    item.created_at = utc_now() - timedelta(days=days)
    test_db.session.commit()


def test_posts_older_than_60_days_are_closed(test_db):
    user_id = _create_user(test_db, "student@example.edu")
    old, recent, already = (_create_item(test_db, user_id, title=t) for t in ("old", "recent", "done"))
    _age_post(test_db, old, 61)
    _age_post(test_db, recent, 59)
    _age_post(test_db, already, 90)
    test_db.session.get(Item, already).resolved = True
    test_db.session.commit()

    assert close_expired_posts() == 1

    test_db.session.expire_all()
    assert test_db.session.get(Item, old).resolved is True
    assert test_db.session.get(Item, recent).resolved is False


def test_backdated_date_reported_does_not_close_a_new_post(test_db):
    """Age comes from when the post was created, which the poster can't change."""
    from datetime import date
    user_id = _create_user(test_db, "student@example.edu")
    post_id = _create_item(test_db, user_id, date_reported=date(2020, 1, 1))

    assert close_expired_posts() == 0
    assert test_db.session.get(Item, post_id).resolved is False


def test_visiting_the_site_closes_expired_posts(app, client, test_db):
    user_id = _create_user(test_db, "student@example.edu")
    post_id = _create_item(test_db, user_id)
    _age_post(test_db, post_id, 61)
    _login(client, "student@example.edu")
    app.extensions.pop("post_expiry", None)

    post = client.get(f"/api/posts/{post_id}").get_json()["post"]

    assert post["resolved"] is True


def test_close_old_posts_command(app, test_db):
    user_id = _create_user(test_db, "student@example.edu")
    _age_post(test_db, _create_item(test_db, user_id), 61)

    result = app.test_cli_runner().invoke(args=["close-old-posts"])

    assert result.exit_code == 0
    assert "Closed 1 post(s) older than 60 days." in result.output
