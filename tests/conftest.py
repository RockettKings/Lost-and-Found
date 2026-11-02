"""Req 40a: shared test setup. Database integration is pending."""
import pytest
from app import create_app


@pytest.fixture
def app():
    # Function scope gives every test its own app and configuration.
    application = create_app()
    application.config.update(TESTING=True)
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_db():

    pytest.skip("Req 40a pending: database library, schema, and test config not implemented")
