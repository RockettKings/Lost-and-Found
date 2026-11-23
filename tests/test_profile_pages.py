"""Requirement 10 pages: Flask's client does not run JavaScript, so check the page
shells and the API data they load. The API itself is tested in test_profiles.py."""

import re

from tests.test_auth import login
from tests.test_pages import _account, _item

OWNER = "owner@example.edu"
OTHER = "other@example.edu"


def _two_users(client, app, test_db):
    # The test register() helper names each account after its email: "owner", "other".
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
    login(client, email=OTHER)
    page = client.get(f"/profiles/{owner_id}").get_data(as_text=True)
    assert f'data-user-id="{owner_id}"' in page
    assets = re.findall(r'(?:href|src)="(/static/[^\"]+)"', page)
    assert "/static/profiles.js" in assets
    for asset in assets:
        assert client.get(asset).status_code == 200

    data = client.get(f"/api/profiles/{owner_id}").json
    assert data["profile"]["username"] == "owner"
    assert {post["title"] for post in data["posts"]} == {"Blue backpack", "Silver keys"}
    assert data["profile"]["stats"]["total_resolved"] == 1


def test_only_the_owner_sees_their_email(client, app, test_db):
    owner_id, _ = _two_users(client, app, test_db)
    login(client, email=OWNER)
    own = client.get(f"/profiles/{owner_id}").get_data(as_text=True)
    assert OWNER in own
    assert "Edit bio" in own and 'href="/auth/username"' in own
    assert "/messages/new" not in own

    client.post("/auth/logout")
    login(client, email=OTHER)
    other = client.get(f"/profiles/{owner_id}").get_data(as_text=True)
    assert OWNER not in other
    assert f'href="/messages/new?to={owner_id}"' in other
    assert "Edit bio" not in other
    assert OWNER not in client.get(f"/api/profiles/{owner_id}").get_data(as_text=True)


def test_signed_out_visitors_are_sent_to_log_in(client, app, test_db):
    owner_id, _ = _two_users(client, app, test_db)
    response = client.get(f"/profiles/{owner_id}")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
    assert client.get(f"/api/profiles/{owner_id}").status_code == 401


def test_unknown_profile_is_404(client, app, test_db):
    _account(client, app, email=OWNER)
    assert client.get("/profiles/999").status_code == 404


def test_header_links_to_my_profile(client, app, test_db):
    owner_id = _account(client, app, email=OWNER)
    home = client.get("/").get_data(as_text=True)
    assert '<a class="nav-user" href="/profiles/me" title="My profile">@owner</a>' in home
    response = client.get("/profiles/me")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/profiles/{owner_id}")


def test_post_detail_links_to_the_poster_without_email(client, app, test_db):
    owner_id = _account(client, app, email=OWNER)
    item = _item(test_db, owner_id)
    client.post("/auth/logout")
    _account(client, app, email=OTHER)
    # posts.js builds the "Posted by" link from these two fields.
    post = client.get(f"/api/posts/{item.id}").json["post"]
    assert (post["author"], post["user_id"]) == ("owner", owner_id)
    assert 'href="/profiles/${Number(post.user_id)}"' in client.get("/static/posts.js").get_data(as_text=True)
    assert OWNER not in client.get(f"/posts/{item.id}").get_data(as_text=True)


def test_edit_page_shows_the_username_and_saves_the_bio(client, app, test_db):
    owner_id = _account(client, app, email=OWNER)
    assert client.patch("/api/profiles/me", json={"bio": "<b>Hi</b>"}).status_code == 200

    page = client.get("/profiles/me/edit").get_data(as_text=True)
    assert 'id="profile-form"' in page
    assert "@owner" in page and 'href="/auth/username"' in page
    assert "&lt;b&gt;Hi&lt;/b&gt;</textarea>" in page
    assert client.get(f"/api/profiles/{owner_id}").json["profile"]["bio"] == "<b>Hi</b>"
