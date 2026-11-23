"""Requirement 21: a signed-in user's history of their own resolved posts."""

from tests.test_auth import login
from tests.test_pages import _account, _item

FIRST = "first@example.edu"
SECOND = "second@example.edu"


def _seed(client, app, test_db):
    first_id = _account(client, app, email=FIRST)
    client.post("/auth/logout")
    second_id = _account(client, app, email=SECOND)
    client.post("/auth/logout")
    _item(test_db, first_id, title="First open")
    _item(test_db, first_id, title="First returned", resolved=True)
    _item(test_db, second_id, title="Second open")
    _item(test_db, second_id, title="Second returned", resolved=True)
    return first_id, second_id


def _history_titles(client, user_id):
    response = client.get(f"/api/profiles/{user_id}?resolved=true")
    assert response.status_code == 200
    return [post["title"] for post in response.json["posts"]]


def test_each_user_sees_only_their_own_resolved_posts(client, app, test_db):
    first_id, second_id = _seed(client, app, test_db)

    for email, user_id, expected in [(FIRST, first_id, ["First returned"]),
                                     (SECOND, second_id, ["Second returned"])]:
        login(client, email=email)
        page = client.get("/profiles/me/history")
        assert page.status_code == 200
        # The page loads the signed-in user's history, whatever the URL asks for.
        assert f'data-user-id="{user_id}"'.encode() in page.data
        assert b"/static/profiles.js" in page.data
        assert _history_titles(client, user_id) == expected
        client.post("/auth/logout")


def test_history_entries_open_their_detail_pages(client, app, test_db):
    first_id, _ = _seed(client, app, test_db)
    login(client, email=FIRST)
    [post] = client.get(f"/api/profiles/{first_id}?resolved=true").json["posts"]
    assert client.get(f"/posts/{post['id']}").status_code == 200


def test_history_requires_login_and_is_linked_from_your_profile(client, app, test_db):
    first_id, second_id = _seed(client, app, test_db)
    assert client.get("/profiles/me/history").status_code == 302

    login(client, email=FIRST)
    assert b'href="/profiles/me/history"' in client.get(f"/profiles/{first_id}").data
    assert b'href="/profiles/me/history"' not in client.get(f"/profiles/{second_id}").data


def test_resolved_filter_only_accepts_true(client, app, test_db):
    first_id, _ = _seed(client, app, test_db)
    login(client, email=FIRST)
    assert client.get(f"/api/profiles/{first_id}?resolved=false").status_code == 400
    assert len(client.get(f"/api/profiles/{first_id}").json["posts"]) == 2
