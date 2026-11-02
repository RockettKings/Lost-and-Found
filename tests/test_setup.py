def test_unknown_url_returns_404(client):
    # No home page exists yet. Use Flask's existing missing-route behavior.
    response = client.get("/__qa_missing_route__")
    assert response.status_code == 404


def test_separate_database_is_configured(test_db):
    """TODO: assert the configured DB is isolated from dev/production."""
    raise NotImplementedError("Replace with a real database-isolation assertion")
