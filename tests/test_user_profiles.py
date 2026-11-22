"""Profile field rules and migration compatibility with existing accounts/posts."""

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Item, User
from tests.conftest import MIGRATIONS


def account(email, **fields):
    user = User(email=email, **fields)
    user.set_password("profile test password")
    return user


# Username rules (length, characters, case-insensitive uniqueness) are in test_usernames.py.

def test_bio_allows_maximum_length_and_is_optional(test_db):
    first = account("one@example.edu", username="first", bio="b" * 500)
    second = account("two@example.edu", username="second")
    test_db.session.add_all([first, second])
    test_db.session.commit()
    test_db.session.expire_all()
    assert len(first.bio) == 500
    assert second.bio is None


def test_database_rejects_oversized_bio(test_db):
    test_db.session.add(account("one@example.edu", username="first", bio="b" * 501))
    with pytest.raises(IntegrityError):
        test_db.session.commit()
    test_db.session.rollback()


def test_profile_migration_preserves_existing_accounts_and_posts(tmp_path):
    app = create_app({
        "TESTING": True, "APP_ENV": "testing", "SECRET_KEY": "migration-test",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'existing.sqlite3'}",
    })
    with app.app_context():
        upgrade(directory=MIGRATIONS, revision="0002")
        password_hash = generate_password_hash("existing password")
        # Use SQL because the old table does not have the new model's columns yet.
        db.session.execute(text(
            "INSERT INTO users (id, email, password_hash, created_at) "
            "VALUES (1, 'existing@example.edu', :hash, '2026-11-01 12:00:00')"
        ), {"hash": password_hash})
        db.session.execute(text(
            "INSERT INTO items (id, user_id, title, description, category, listing_type, "
            "general_location, date_reported, created_at, resolved) "
            "VALUES (1, 1, 'Backpack', 'Blue bag', 'bags', 'lost', 'Library', "
            "'2026-11-01', '2026-11-01 12:00:00', 0)"
        ))
        db.session.commit()
        db.session.remove()

        upgrade(directory=MIGRATIONS)
        user = db.session.get(User, 1)
        assert user.email == "existing@example.edu"
        assert user.password_hash == password_hash
        assert user.check_password("existing password")
        # Migration 0008 gives existing accounts a username that reveals nothing private.
        assert user.username == "user1" and user.bio is None
        assert db.session.get(Item, 1).user.id == user.id
        assert db.session.execute(text("PRAGMA foreign_key_check")).all() == []
        user.username = "Andrew"
        user.bio = "Student"
        db.session.commit()
        db.session.remove()

        # Reversing/reapplying removes only the new fields, preserving account data.
        downgrade(directory=MIGRATIONS, revision="0002")
        columns = {column["name"] for column in inspect(db.engine).get_columns("users")}
        assert not {"display_name", "bio", "username"} & columns
        assert db.session.execute(text("SELECT title FROM items WHERE user_id = 1")).scalar_one() == "Backpack"
        db.session.remove()
        upgrade(directory=MIGRATIONS)
        assert db.session.get(User, 1).password_hash == password_hash
        db.session.remove()
        db.engine.dispose()
