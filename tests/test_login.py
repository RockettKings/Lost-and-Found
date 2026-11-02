import pytest


@pytest.mark.skip(reason="Req 40c pending: account routes and database are not implemented")
def test_valid_login(client, test_db):
    """Create a user with a hashed password. Submit valid credentials. Verify authenticated identity or access to a protected route."""
    raise NotImplementedError("Implement against the team's account API")


@pytest.mark.skip(reason="Req 40c pending: account routes and database are not implemented")
def test_wrong_password(client, test_db):
    """Create a user and submit an incorrect password. Verify the Invalid email or password error and unauthenticated state."""
    raise NotImplementedError("Implement against the team's account API")


@pytest.mark.skip(reason="Req 40c pending: account routes and database are not implemented")
def test_unknown_email(client, test_db):
    """Submit an unregistered email. Verify the same Invalid email or password error and unauthenticated state."""
    raise NotImplementedError("Implement against the team's account API")


@pytest.mark.skip(reason="Req 40c pending: account routes and database are not implemented")
def test_logout(client, test_db):
    """Log in successfully, log out, then verify unauthenticated state and rejection from an existing protected route."""
    raise NotImplementedError("Implement against the team's account API")

