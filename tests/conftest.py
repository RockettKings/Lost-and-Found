"""Every database test gets a separate migrated file under pytest's temp directory."""

from pathlib import Path

import pytest
from flask_migrate import upgrade

from app import create_app
from app.extensions import db


MIGRATIONS = str(Path(__file__).resolve().parents[1] / "migrations")


@pytest.fixture
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "APP_ENV": "testing",
        "SECRET_KEY": "database-tests-only",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.sqlite3'}",
        "S3_BUCKET": "test-bucket",
    })
    with application.app_context():
        upgrade(directory=MIGRATIONS)
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_db(app):
    # Compatible fixture name for F's account tests when they are integrated.
    with app.app_context():
        yield db
        db.session.remove()
