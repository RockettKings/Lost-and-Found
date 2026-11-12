
from datetime import date
import re

from app.models import Item, User

TEST_PASSWORD = "posts test password"


def test_browser_post_request_requires_csrf_header(client, app):
    """Use the real form's meta token, just as posts.js does in the browser."""
    client.post("/auth/register", data={
        "email": "browser@example.edu", "password": TEST_PASSWORD, "confirm": TEST_PASSWORD,
    })
    app.config["WTF_CSRF_ENABLED"] = True
    rejected = client.post("/api/posts/", json=_valid_post_data())
    assert rejected.status_code == 400
    assert rejected.is_json
    assert "CSRF" in rejected.json["error"]

    page = client.get("/posts/new").get_data(as_text=True)
    token = re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)
    accepted = client.post("/api/posts/", data=_valid_post_data(),
                           headers={"X-CSRFToken": token})
    assert accepted.status_code == 201


def test_unknown_api_route_returns_json(client):
    response = client.get("/api/posts/missing-route")
    assert response.status_code == 404
    assert response.is_json
    assert "error" in response.json


# HELPER FUNCTIONS
# ----------------

def _create_user(test_db, email):
    """Create a user in the database and return their ID."""
    user = User(email=email)
    user.set_password(TEST_PASSWORD)

    test_db.session.add(user)
    test_db.session.commit()

    return user.id


def _create_item(
    test_db,
    user_id,
    title="Backpack",
    description="Blue backpack",
    category="bags",
    listing_type="lost",
    general_location="Library",
    date_reported=date(2026, 11, 8),
):
    """Create a post in the database and return its ID."""
    item = Item(
        user_id=user_id,
        title=title,
        description=description,
        category=category,
        listing_type=listing_type,
        general_location=general_location,
        date_reported=date_reported,
    )

    test_db.session.add(item)
    test_db.session.commit()

    return item.id


def _login(client, email):
    """Log in a user."""
    response = client.post(
        "/auth/login",
        data={"email": email, "password": TEST_PASSWORD},
    )

    assert response.status_code == 302


def _valid_post_data():
    """Return valid example post data."""
    return {
        "title": "Lost wallet",
        "description": "Black leather wallet",
        "category": "Accessories",
        "listing_type": "lost",
        "general_location": "Cafeteria",
        "date_reported": "2026-11-08",
    }


# GET POST TESTS
# --------------

def test_get_posts_empty_list(client):
    """Test GET /api/posts/ with an empty database."""
    response = client.get("/api/posts/")

    assert response.status_code == 200
    assert response.get_json() == {"posts": []}


def test_get_posts_with_filters(client, test_db):
    user_id = _create_user(test_db, "student@example.edu")

    _create_item(
        test_db,
        user_id,
        title="Backpack",
        category="bags",
        listing_type="lost",
    )
    _create_item(
        test_db,
        user_id,
        title="Laptop",
        category="electronics",
        listing_type="found",
    )

    response = client.get("/api/posts/?category=bags&listing_type=LOST")

    assert response.status_code == 200

    posts = response.get_json()["posts"]
    assert len(posts) == 1
    assert posts[0]["title"] == "Backpack"


def test_get_posts_with_keyword_search(client, test_db):
    user_id = _create_user(test_db, "student@example.edu")

    _create_item(
        test_db,
        user_id,
        title="Backpack",
        description="Blue bag left in the library",
    )
    _create_item(
        test_db,
        user_id,
        title="Laptop",
        description="Silver laptop found in the lab",
    )

    response = client.get("/api/posts/?q=LIBRARY")

    assert response.status_code == 200

    posts = response.get_json()["posts"]
    assert len(posts) == 1
    assert posts[0]["title"] == "Backpack"


def test_get_posts_reject_invalid_listing_type(client):
    response = client.get("/api/posts/?listing_type=other")

    assert response.status_code == 400


def test_get_posts_reject_invalid_sort(client):
    response = client.get("/api/posts/?sort=random")

    assert response.status_code == 400


def test_get_post_returns_existing_post(client, test_db):
    user_id = _create_user(test_db, "student@example.edu")
    post_id = _create_item(test_db, user_id)

    response = client.get(f"/api/posts/{post_id}")

    assert response.status_code == 200

    post = response.get_json()["post"]
    assert post["id"] == post_id
    assert post["title"] == "Backpack"
    assert post["date_reported"] == "2026-11-08"
    assert post["photo_url"] is None


def test_get_post_invalid_id(client):
    response = client.get("/api/posts/9999")

    assert response.status_code == 404


# CREATE POST TESTS
# -----------------

def test_create_post_requires_login(client):
    response = client.post("/api/posts/", json=_valid_post_data())

    assert response.status_code == 401


def test_create_post_success(client, test_db):
    user_id = _create_user(test_db, "student@example.edu")
    _login(client, "student@example.edu")

    response = client.post("/api/posts/", json=_valid_post_data())

    assert response.status_code == 201

    created_post = response.get_json()["post"]

    assert created_post["title"] == "Lost wallet"
    assert created_post["listing_type"] == "lost"
    assert created_post["date_reported"] == "2026-11-08"
    assert created_post["is_owner"] is True

    saved_item = test_db.session.get(Item, created_post["id"])

    assert saved_item is not None
    assert saved_item.user_id == user_id


def test_create_post_reject_invalid_title(client, test_db):
    _create_user(test_db, "student@example.edu")
    _login(client, "student@example.edu")

    data = _valid_post_data()
    data["title"] = "  "

    response = client.post("/api/posts/", json=data)

    assert response.status_code == 400
    assert "title" in response.get_json()["errors"]


def test_create_post_requires_date_reported(client, test_db):
    _create_user(test_db, "student@example.edu")
    _login(client, "student@example.edu")

    data = _valid_post_data()
    del data["date_reported"]

    response = client.post("/api/posts/", json=data)

    assert response.status_code == 400
    assert "date_reported" in response.get_json()["errors"]


def test_create_post_reject_invalid_date(client, test_db):
    _create_user(test_db, "student@example.edu")
    _login(client, "student@example.edu")

    data = _valid_post_data()
    data["date_reported"] = "not-a-date"

    response = client.post("/api/posts/", json=data)

    assert response.status_code == 400
    assert "date_reported" in response.get_json()["errors"]


def test_create_post_reject_user_id_from_client(client, test_db):
    _create_user(test_db, "student@example.edu")
    _login(client, "student@example.edu")

    data = _valid_post_data()
    data["user_id"] = 999

    response = client.post("/api/posts/", json=data)

    assert response.status_code == 400
    assert "body" in response.get_json()["errors"]


# UPDATE POST TESTS
# -----------------

def test_update_post_requires_login(client):
    response = client.patch(
        "/api/posts/1",
        json={"title": "Updated title"},
    )

    assert response.status_code == 401


def test_update_post_changes_only_submitted_fields(client, test_db):
    user_id = _create_user(test_db, "student@example.edu")
    post_id = _create_item(test_db, user_id)

    _login(client, "student@example.edu")

    response = client.patch(
        f"/api/posts/{post_id}",
        json={"description": "Red backpack"},
    )

    assert response.status_code == 200

    updated_post = response.get_json()["post"]

    assert updated_post["description"] == "Red backpack"
    assert updated_post["title"] == "Backpack"
    assert updated_post["category"] == "bags"
    assert updated_post["is_owner"] is True


def test_update_post_can_mark_resolved(client, test_db):
    user_id = _create_user(test_db, "student@example.edu")
    post_id = _create_item(test_db, user_id)

    _login(client, "student@example.edu")

    response = client.patch(
        f"/api/posts/{post_id}",
        json={"resolved": True},
    )

    assert response.status_code == 200
    assert response.get_json()["post"]["resolved"] is True

    test_db.session.expire_all()
    saved_item = test_db.session.get(Item, post_id)

    assert saved_item.resolved is True


def test_update_post_forbids_non_owner(client, test_db):
    owner_id = _create_user(test_db, "student@example.edu")
    _create_user(test_db, "other@example.edu")

    post_id = _create_item(test_db, owner_id)

    _login(client, "other@example.edu")

    response = client.patch(
        f"/api/posts/{post_id}",
        json={"title": "Unauthorized change"},
    )

    assert response.status_code == 403


def test_update_post_rejects_empty_data(client, test_db):
    user_id = _create_user(test_db, "student@example.edu")
    post_id = _create_item(test_db, user_id)

    _login(client, "student@example.edu")

    response = client.patch(f"/api/posts/{post_id}", json={})

    assert response.status_code == 400


# DELETE POST TESTS
# -----------------

def test_delete_post_requires_login(client):
    response = client.delete("/api/posts/1")

    assert response.status_code == 401


def test_delete_post_success(client, test_db):
    user_id = _create_user(test_db, "student@example.edu")
    post_id = _create_item(test_db, user_id)

    _login(client, "student@example.edu")

    response = client.delete(f"/api/posts/{post_id}")

    assert response.status_code == 204
    assert response.data == b""

    test_db.session.expire_all()

    assert test_db.session.get(Item, post_id) is None


def test_delete_post_forbids_non_owner(client, test_db):
    owner_id = _create_user(test_db, "student@example.edu")
    _create_user(test_db, "other@example.edu")

    post_id = _create_item(test_db, owner_id)

    _login(client, "other@example.edu")

    response = client.delete(f"/api/posts/{post_id}")

    assert response.status_code == 403

    test_db.session.expire_all()

    assert test_db.session.get(Item, post_id) is not None
