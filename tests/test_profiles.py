"""Requirement 10: viewing profiles, and editing your own display name and bio."""

from app.models import User
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


def test_owner_sees_their_posts_and_email(client, app, test_db):
    owner_id, _ = _two_users(client, app, test_db)
    login(client, email=OWNER)
    page = client.get(f"/profiles/{owner_id}").get_data(as_text=True)
    assert "Blue backpack" in page and "Silver keys" in page
    assert "umbrella" not in page
    assert OWNER in page
    assert "Edit profile" in page
    assert "/messages/new" not in page


def test_other_users_see_posts_but_never_the_email(client, app, test_db):
    owner_id, _ = _two_users(client, app, test_db)
    login(client, email=OTHER)
    page = client.get(f"/profiles/{owner_id}").get_data(as_text=True)
    assert "Blue backpack" in page and "Silver keys" in page
    assert OWNER not in page
    assert f'href="/messages/new?to={owner_id}"' in page
    assert "Edit profile" not in page

    client.post("/auth/logout")
    public = client.get(f"/profiles/{owner_id}").get_data(as_text=True)
    assert "Blue backpack" in public
    assert OWNER not in public
    assert "/messages/new" not in public


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


def test_edit_profile_sets_the_public_name_and_bio(client, app, test_db):
    owner_id = _account(client, app, email=OWNER)
    response = client.post("/profiles/me/edit", data={"display_name": "  Jonathan  ", "bio": "Lost my keys a lot."})
    assert response.status_code == 303
    client.post("/auth/logout")
    page = client.get(f"/profiles/{owner_id}").get_data(as_text=True)
    assert "<h1>Jonathan</h1>" in page
    assert "Lost my keys a lot." in page

    with app.app_context():
        from app.extensions import db
        user = db.session.get(User, owner_id)
        assert (user.display_name, user.bio) == ("Jonathan", "Lost my keys a lot.")


def test_taken_or_too_long_display_name_is_rejected(client, app, test_db):
    _account(client, app, email=OWNER)
    client.post("/profiles/me/edit", data={"display_name": "Jonathan", "bio": ""})
    client.post("/auth/logout")
    other_id = _account(client, app, email=OTHER)

    taken = client.post("/profiles/me/edit", data={"display_name": "JONATHAN", "bio": ""})
    assert taken.status_code == 400
    assert b"already taken" in taken.data
    too_long = client.post("/profiles/me/edit", data={"display_name": "x" * 81, "bio": ""})
    assert too_long.status_code == 400

    with app.app_context():
        from app.extensions import db
        assert db.session.get(User, other_id).display_name is None
