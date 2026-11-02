import pytest


@pytest.mark.skip(reason="Req 40b pending: account routes and database are not implemented")
def test_valid_registration(client, test_db):
    """Submit valid username, email, password, and confirmation. Verify success, exactly one saved user, and a verifiable password hash."""
    raise NotImplementedError("Implement against the team's account API")


@pytest.mark.skip(reason="Req 40b pending: account routes and database are not implemented")
def test_duplicate_email(client, test_db):
    """Create a user, then submit a different username with the same email. Verify rejection and no extra user."""
    raise NotImplementedError("Implement against the team's account API")


@pytest.mark.skip(reason="Req 40b pending: account routes and database are not implemented")
def test_duplicate_username(client, test_db):
    """Create a user, then submit a different email with the same username. Verify rejection and no extra user."""
    raise NotImplementedError("Implement against the team's account API")


@pytest.mark.skip(reason="Req 40b pending: account routes and database are not implemented")
def test_mismatched_passwords(client, test_db):
    """Submit otherwise valid details with different password and confirmation. Verify rejection and no saved user."""
    raise NotImplementedError("Implement against the team's account API")

