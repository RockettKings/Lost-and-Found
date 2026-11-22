from datetime import date
import pytest

from app.models import Item, User

TEST_PASSWORD = "profile test password"

## HELPER FUNCTIONS

def _create_user(test_db, email, display_name, bio=None):
    """Create a user in the database and return their ID."""

    user = User(email=email, display_name=display_name, bio=bio)
    user.set_password(TEST_PASSWORD)

    test_db.session.add(user)
    test_db.session.commit()

    return user.id

def _create_item(test_db, user_id, title="Backpack", listing_type="lost", resolved=False):
    """Create a post in the database and return its ID."""

    item = Item(
        user_id=user_id,
        title=title,
        description="Placeholder",
        category="bags",
        listing_type=listing_type,
        general_location="Library",
        date_reported=date(2026, 11, 8),
        resolved=resolved
    )

    test_db.session.add(item)
    test_db.session.commit()

    return item.id

def _login(client, email):
    """Log in a user."""

    response = client.post("/auth/login", data={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 302

## GET TESTS

def test_get_profile_success(client, test_db):
    """Ensure that a user can successfully retrieve a user profile."""

    user_id = _create_user(test_db, "student@example.edu", "Student")
    other_user_id = _create_user(test_db, "other@example.edu", "Other")

    # Create dummy posts
    _create_item(test_db, user_id, "Backpack", "lost")
    _create_item(test_db, user_id, "Wallet", "found", resolved=True)
    _create_item(test_db, other_user_id, "Laptop", "found", resolved=True)

    response = client.get(f"/api/profiles/{user_id}")
    assert response.status_code == 200

    data = response.get_json()
    profile = data["profile"]

    assert profile["id"] == user_id
    assert profile["display_name"] == "Student"
    assert profile["bio"] is None
    assert profile["is_owner"] is False
    assert profile["stats"] == {
        "total_posts": 2,
        "total_lost": 1,
        "total_found": 1,
        "total_resolved": 1
    }

    # Verify that the other user's posts are not returned
    posts = data["posts"]
    assert len(posts) == 2
    assert all(post["user_id"] == user_id for post in posts)
    assert all(post["is_owner"] is False for post in posts)

    # Verify pagination
    pagination = data["pagination"]
    assert pagination["page"] == 1
    assert pagination["per_page"] == 10
    assert pagination["total"] == 2
    assert pagination["has_next"] is False
    assert pagination["has_prev"] is False

def test_private_information_kept_safe(client, test_db):
    user_id = _create_user(test_db, "student@example.edu", "Student")
    response = client.get(f"/api/profiles/{user_id}")
    assert response.status_code == 200

    profile = response.get_json()["profile"]
    assert "email" not in profile
    assert "password_hash" not in profile

def test_profile_not_found(client):
    response = client.get("/api/profiles/9999")
    assert response.status_code == 404
    assert response.get_json()["error"] == "User not found."

def test_profile_without_posts(client, test_db):
    user_id = _create_user(test_db, "student@example.edu", "Student")
    response = client.get(f"/api/profiles/{user_id}")
    assert response.status_code == 200

    data = response.get_json()
    assert data["posts"] == []
    assert data["profile"]["stats"] == {
        "total_posts": 0,
        "total_lost": 0,
        "total_found": 0,
        "total_resolved": 0
    }

def test_get_own_profile(client, test_db):
    user_id = _create_user(test_db, "student@example.edu", "Student")
    _create_item(test_db, user_id)
    _login(client, "student@example.edu")
    response = client.get(f"/api/profiles/{user_id}")
    assert response.status_code == 200

    data = response.get_json()
    assert data["profile"]["is_owner"] is True
    assert data["posts"][0]["is_owner"] is True

def test_get_other_users_profile(client, test_db):
    owner_id = _create_user(test_db, "owner@example.edu", "Owner")
    _create_user(test_db, "other@example.edu", "Other")
    _create_item(test_db, owner_id)
    _login(client, "other@example.edu")
    response = client.get(f"/api/profiles/{owner_id}")
    assert response.status_code == 200

    data = response.get_json()
    assert data["profile"]["is_owner"] is False
    assert data["posts"][0]["is_owner"] is False

def test_profile_pagination(client, test_db):
    user_id = _create_user(test_db, "student@example.edu", "Student")
    for i in range(15):
        _create_item(test_db, user_id, title=f"Item {i}")

    # Retrieve first page
    response1 = client.get(f"/api/profiles/{user_id}?page=1&per_page=10")
    assert response1.status_code == 200

    data1 = response1.get_json()
    pagination1 = data1["pagination"]
    assert len(data1["posts"]) == 10
    assert pagination1["page"] == 1
    assert pagination1["total"] == 15
    assert pagination1["pages"] == 2
    assert pagination1["has_next"] is True
    assert pagination1["has_prev"] is False

    # Retrieve second page
    response2 = client.get(f"/api/profiles/{user_id}?page=2&per_page=10")
    assert response2.status_code == 200

    data2 = response2.get_json()
    pagination2 = data2["pagination"]
    assert len(data2["posts"]) == 5
    assert pagination2["page"] == 2
    assert pagination2["has_next"] is False
    assert pagination2["has_prev"] is True

    # Verify each page contains different posts
    page1_ids = {post["id"] for post in data1["posts"]}
    page2_ids = {post["id"] for post in data2["posts"]}

    assert page1_ids.isdisjoint(page2_ids)

def test_max_per_page(client, test_db):
    user_id = _create_user(test_db, "student@example.edu", "Student")

    items = [Item(
        user_id=user_id,
        title=f"Item {i}",
        description="Placeholder",
        category="bags",
        listing_type="lost",
        general_location="Libary",
        date_reported=date(2026, 11, 8))
        for i in range(51)]

    test_db.session.add_all(items)
    test_db.session.commit()

    response = client.get(f"/api/profiles/{user_id}?per_page=100")
    assert response.status_code == 200

    data = response.get_json()
    assert data["pagination"]["per_page"] == 50
    assert len(data["posts"]) == 50
    assert data["pagination"]["total"] == 51

@pytest.mark.parametrize("query", [
    "page=0",
    "page=-1",
    "page=abc",
    "per_page=0",
    "per_page=-5",
    "per_page=abc"
])
def test_invalid_pagination(client, test_db, query):
    user_id = _create_user(test_db, "student@example.edu", "Student")
    response = client.get(f"/api/profiles/{user_id}?{query}")
    assert response.status_code == 400

def test_invalid_page(client, test_db):
    user_id = _create_user(test_db, "student@example.edu", "Student")
    _create_item(test_db, user_id)
    response = client.get(f"/api/profiles/{user_id}?page=2")
    assert response.status_code == 404

def test_profile_resolved_posts(client, test_db):
    user_id = _create_user(test_db, "student@example.edu", "Student")
    _create_item(test_db, user_id, "Backpack", "lost", resolved=False)
    _create_item(test_db, user_id, "Wallet", "found", resolved=True)
    response = client.get(f"/api/profiles/{user_id}?resolved=true")
    assert response.status_code == 200

    data = response.get_json()
    assert len(data["posts"]) == 1
    assert data["posts"][0]["title"] == "Wallet"
    assert data["posts"][0]["resolved"] is True
    assert data["profile"]["stats"]["total_posts"] == 2

## PATCH TESTS

def test_login_required(client):
    response = client.patch("/api/profiles/me", json={"bio": "Updated bio"})
    assert response.status_code == 401

def test_edit_profile_success(client, test_db):
    user_id = _create_user(test_db, "student@example.edu", "Old name", "Old bio")
    _login(client, "student@example.edu")
    response = client.patch(f"/api/profiles/me",
                          json={"display_name": "New name", "bio": "New bio"})
    assert response.status_code == 200

    profile = response.get_json()["profile"]
    assert profile["id"] == user_id
    assert profile["display_name"] == "New name"
    assert profile["bio"] == "New bio"
    assert profile["is_owner"] is True

    # Verify changes are saved in the database
    test_db.session.expire_all()
    saved_user = test_db.session.get(User, user_id)
    assert saved_user.display_name == "New name"
    assert saved_user.bio == "New bio"

@pytest.mark.parametrize("data, expected_name, expected_bio", [
    ({"display_name": "New name"}, "New name", "Old bio"),
    ({"bio": "New bio"}, "Old name", "New bio")
])
def test_partial_update(client, test_db, data, expected_name, expected_bio):
    _create_user(test_db, "student@example.edu", "Old name", "Old bio")
    _login(client, "student@example.edu")
    response = client.patch("/api/profiles/me", json=data)
    assert response.status_code == 200

    profile = response.get_json()["profile"]
    assert profile["display_name"] == expected_name
    assert profile["bio"] == expected_bio

@pytest.mark.parametrize("bio", [None, "", "    "])
def test_clear_bio(client, test_db, bio):
    user_id = _create_user(test_db, "student@example.edu", "Student", "Old bio")
    _login(client, "student@example.edu")
    response = client.patch("/api/profiles/me", json={"bio": bio})
    assert response.status_code == 200
    assert response.get_json()["profile"]["bio"] is None

    test_db.session.expire_all()
    saved_user = test_db.session.get(User, user_id)
    assert saved_user.bio is None

def test_duplicate_display_name(client, test_db):
    _create_user(test_db, "first@example.edu", "John")
    _create_user(test_db, "second@example.edu", "Smith")
    _login(client, "second@example.edu")
    response = client.patch("/api/profiles/me", json={"display_name": "john"})
    assert response.status_code == 409
    
    assert "display_name" in response.get_json()["errors"]

def test_keep_existing_display_name(client, test_db):
    _create_user(test_db, "student@example.edu", "Student")
    _login(client, "student@example.edu")
    response = client.patch("/api/profiles/me", json={"display_name": "Student"})
    assert response.status_code == 200
    assert response.get_json()["profile"]["display_name"] == "Student"

## VALIDATION TESTS

@pytest.mark.parametrize("dname", [None, 123, "", "  ", "x"*81])
def test_invalid_display_names(client, test_db, dname):
    _create_user(test_db, "student@example.edu", "Student")
    _login(client, "student@example.edu")
    response = client.patch("/api/profiles/me", json={"display_name": dname})
    assert response.status_code == 400
    assert "display_name" in response.get_json()["errors"]

@pytest.mark.parametrize("bio", [123, True, "x"*501])
def test_invalid_bio_descriptions(client, test_db, bio):
    _create_user(test_db, "student@example.edu", "Student")
    _login(client, "student@example.edu")
    response = client.patch("/api/profiles/me", json={"bio": bio})
    assert response.status_code == 400
    assert "bio" in response.get_json()["errors"]

@pytest.mark.parametrize("data", [{}, {"email": "new@example.edu"}, {"user_id": 999}])
def test_invalid_fields(client, test_db, data):
    _create_user(test_db, "student@example.edu", "Student")
    _login(client, "student@example.edu")
    response = client.patch("/api/profiles/me", json=data)
    assert response.status_code == 400
    assert "body" in response.get_json()["errors"]

def test_reject_non_json(client, test_db):
    _create_user(test_db, "student@example.edu", "Student")
    _login(client, "student@example.edu")
    response = client.patch("/api/profiles/me", data={"bio": "Updated bio"})
    assert response.status_code == 400

def test_malformed_json(client, test_db):
    _create_user(test_db, "student@example.edu", "Student")
    _login(client, "student@example.edu")
    response = client.patch("/api/profiles/me", data="{invalid json", content_type="application/json")
    assert response.status_code == 400