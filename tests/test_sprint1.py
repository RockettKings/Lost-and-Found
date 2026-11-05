"""Only C's Sprint 1 database, configuration, and photo-storage integration."""

from unittest.mock import Mock

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app import create_app, storage
from app.models import Item, User


@pytest.fixture
def item(test_db):
    user = User(email="student@example.edu", password_hash=generate_password_hash("test password"))
    post = Item(user=user, title="Backpack", description="Blue backpack",
                category="bags", listing_type="lost", general_location="Library")
    test_db.session.add(post)
    test_db.session.commit()
    return post


def test_migrated_records_survive_restart(app, test_db, item):
    assert set(inspect(test_db.engine).get_table_names()) == {"users", "items", "alembic_version"}
    item_id = item.id
    restarted = create_app(dict(app.config))
    with restarted.app_context():
        saved = test_db.session.get(Item, item_id)
        assert saved.title == "Backpack"
        assert saved.user.email == "student@example.edu"
        test_db.session.remove()
        test_db.engine.dispose()


def test_duplicate_email_is_rejected(test_db, item):
    test_db.session.add(User(email=" STUDENT@EXAMPLE.EDU ", password_hash=item.user.password_hash))
    with pytest.raises(IntegrityError):
        test_db.session.commit()
    test_db.session.rollback()


@pytest.mark.parametrize("field,value", [
    ("user_id", 999999), ("listing_type", "unknown"),
    ("title", ""), ("title", "x" * 121),
])
def test_invalid_item_records_are_rejected(test_db, item, field, value):
    setattr(item, field, value)
    with pytest.raises(IntegrityError):
        test_db.session.commit()
    test_db.session.rollback()


def test_health(client):
    assert client.get("/healthz").json == {"status": "ok"}


@pytest.mark.parametrize("overrides", [
    {"SECRET_KEY": None}, {"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"},
])
def test_production_requires_secret_and_persistent_path(tmp_path, overrides):
    config = {"APP_ENV": "production", "SECRET_KEY": "a" * 64,
              "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'prod.sqlite3'}"}
    config.update(overrides)
    with pytest.raises(ValueError):
        create_app(config)


def test_photo_storage_handoff_without_contacting_aws(app, monkeypatch):
    s3 = Mock()
    monkeypatch.setattr(storage.boto3, "client", Mock(return_value=s3))
    jpeg = b"\xff\xd8processed-by-E\xff\xd9"
    with app.app_context():
        key = storage.save_photo(jpeg)
        s3.put_object.assert_called_once_with(
            Bucket="test-bucket", Key=key, Body=jpeg,
            ContentType="image/jpeg", ServerSideEncryption="AES256")
        storage.photo_url(key)
        s3.generate_presigned_url.assert_called_once_with(
            "get_object", Params={"Bucket": "test-bucket", "Key": key}, ExpiresIn=900)
        storage.delete_photo(key)
        s3.delete_object.assert_called_once_with(Bucket="test-bucket", Key=key)
        with pytest.raises(ValueError):
            storage.save_photo(b"not-a-jpeg")
        with pytest.raises(ValueError):
            storage.photo_url("other-private-file")
