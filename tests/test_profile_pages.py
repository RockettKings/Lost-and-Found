"""Requirement 10 pages: Flask's client does not run JavaScript, so check the page
shells and the API data they load. The API itself is tested in test_profiles.py."""

import re

from tests.test_auth import login
from tests.test_pages import _account, _item

OWNER = "owner@example.edu"
OTHER = "other@example.edu"


def _two_users(client, app, test_db):
    owner_id = _account(client, app, email=OWNER)
    client.post("/auth/logout")
    other_id = _account(client, app, email=OTHER)
    client.post("/auth/logout")
    _item(test_db, owner_id, title="Blue backpack")
    _item(test_db, owner_id, title="Silver keys", listing_type="found", resolved=True)
    _item(test_db, other_id, title="Someone else's umbrella")
    return owner_id, other_id


def test_profile_page_loads_its_script_and_data(client, app, test_db):
    owner_id, _ = _two_users(client, app, test_db)
    page = client.get(f"/profiles/{owner_id}").get_data(as_text=True)
    assert f'data-user-id="{owner_id}"' in page
    assets = re.findall(r'(?:href|src)="(/static/[^\"]+)"', page)
    assert "/static/profiles.js" in assets
    for asset in assets:
        assert client.get(asset).status_code == 200

    data = client.get(f"/api/profiles/{owner_id}").json
    assert {post["title"] for post in data["posts"]} == {"Blue backpack", "Silver keys"}
    assert data["profile"]["stats"]["total_resolved"] == 1


def test_only_the_owner_sees_their_email(client, app, test_db):
    owner_id, _ = _two_users(client, app, test_db)
    login(client, email=OWNER)
    own = client.get(f"/profiles/{owner_id}").get_data(as_text=True)
    assert OWNER in own
    assert "Edit profile" in own
    assert "/messages/new" not in own

    client.post("/auth/logout")
    login(client, email=OTHER)
    other = client.get(f"/profiles/{owner_id}").get_data(as_text=True)
    assert OWNER not in other and OTHER not in other
    assert f'href="/messages/new?to={owner_id}"' in other
    assert "Edit profile" not in other
    assert OWNER not in client.get(f"/api/profiles/{owner_id}").get_data(as_text=True)

    client.post("/auth/logout")
    public = client.get(f"/profiles/{owner_id}").get_data(as_text=True)
    assert OWNER not in public
    assert "/messages/new" not in public
    assert "Log in to send a message" in public


def test_unknown_profile_is_404(client, test_db):
    assert client.get("/profiles/999").status_code == 404


def test_account_link_and_my_profile_redirect(client, app, test_db):
    owner_id = _account(client, app, email=OWNER)
    assert b'href="/profiles/me"' in client.get("/").data
    response = client.get("/profiles/me")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/profiles/{owner_id}")
    client.post("/auth/logout")
    assert client.get("/profiles/me").status_code == 302
    assert client.get("/profiles/me/edit").status_code == 302


def test_post_detail_links_to_the_poster_without_email(client, app, test_db):
    owner_id = _account(client, app, email=OWNER)
    item = _item(test_db, owner_id)
    client.post("/auth/logout")
    page = client.get(f"/posts/{item.id}").get_data(as_text=True)
    assert f'href="/profiles/{owner_id}">User #{owner_id}</a>' in page
    assert OWNER not in page


def test_edit_page_shows_current_values_and_saves_through_the_api(client, app, test_db):
    owner_id = _account(client, app, email=OWNER)
    assert client.patch("/api/profiles/me", json={"display_name": "Jonathan", "bio": "<b>Hi</b>"}).status_code == 200

    page = client.get("/profiles/me/edit").get_data(as_text=True)
    assert 'id="profile-form"' in page
    assert 'value="Jonathan"' in page
    assert "&lt;b&gt;Hi&lt;/b&gt;</textarea>" in page

    client.post("/auth/logout")
    detail_owner = client.get(f"/api/profiles/{owner_id}").json["profile"]
    assert detail_owner["display_name"] == "Jonathan"
