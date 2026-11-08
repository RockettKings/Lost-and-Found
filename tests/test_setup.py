from pathlib import Path


def test_unknown_url_returns_404(client):
    response = client.get("/__qa_missing_route__")
    assert response.status_code == 404


def test_separate_database_is_configured(test_db, tmp_path):
    url = test_db.engine.url
    expected = tmp_path / "test.sqlite3"

    assert url.get_backend_name() == "sqlite"
    assert Path(url.database).resolve() == expected.resolve()
    assert expected.is_file()
