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


def test_profile_fields_keep_display_case_and_allow_maximum_lengths(test_db):
    name = "A" * 80
    user = account("one@example.edu", display_name=f"  {name}  ", bio="b" * 500)
    test_db.session.add(user)
    test_db.session.commit()
    test_db.session.expire_all()
    assert user.display_name == name
    assert len(user.bio) == 500


@pytest.mark.parametrize("duplicate", ["Andrew", "andrew", "  ANDREW  "])
def test_display_names_are_unique(test_db, duplicate):
    test_db.session.add(account("one@example.edu", display_name="Andrew"))
    test_db.session.commit()
    test_db.session.add(account("two@example.edu", display_name=duplicate))
    with pytest.raises(IntegrityError):
        test_db.session.commit()
    test_db.session.rollback()
    assert len(test_db.session.execute(test_db.select(User)).scalars().all()) == 1


def test_accounts_can_leave_profiles_unset(test_db):
    first = account("one@example.edu")
    second = account("two@example.edu", display_name=" \t ", bio="")
    test_db.session.add_all([first, second])
    test_db.session.commit()
    assert first.display_name is None and second.display_name is None
    assert first.bio is None and second.bio == ""


@pytest.mark.parametrize("values", [
    {"display_name": "a" * 81}, {"bio": "b" * 501},
])
def test_database_rejects_oversized_profile_fields(test_db, values):
    test_db.session.add(account("one@example.edu", **values))
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
        assert user.display_name is None and user.bio is None
        assert db.session.get(Item, 1).user.id == user.id
        assert db.session.execute(text("PRAGMA foreign_key_check")).all() == []
        user.display_name = "Andrew"
        user.bio = "Student"
        db.session.commit()
        db.session.remove()

        # Reversing/reapplying removes only the new fields, preserving account data.
        downgrade(directory=MIGRATIONS, revision="0002")
        assert "display_name" not in {column["name"] for column in inspect(db.engine).get_columns("users")}
        assert db.session.execute(text("SELECT title FROM items WHERE user_id = 1")).scalar_one() == "Backpack"
        db.session.remove()
        upgrade(directory=MIGRATIONS)
        assert db.session.get(User, 1).password_hash == password_hash
        db.session.remove()
        db.engine.dispose()
