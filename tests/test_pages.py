"""HTML pages for browsing, viewing, and managing posts."""

from datetime import date
from io import BytesIO

from app.models import Item, User
from tests.test_auth import GOOD_PASSWORD, login, register

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


def _account(client, app, email="student@example.edu"):
    register(client, email=email)
    with app.app_context():
        from app.extensions import db
        return db.session.execute(db.select(User).filter_by(email=email)).scalar_one().id


def _item(test_db, user_id, **overrides):
    fields = {
        "title": "Blue backpack",
        "description": "Lost near the library",
        "category": "bags",
        "listing_type": "lost",
        "general_location": "Library",
        "date_reported": date(2026, 1, 2),
    }
    fields.update(overrides)
    item = Item(user_id=user_id, **fields)
    test_db.session.add(item)
    test_db.session.commit()
    return item


def _form(title="Lost wallet", **overrides):
    data = {
        "title": title,
        "description": "Black leather wallet",
        "category": "Accessories",
        "listing_type": "lost",
        "general_location": "Cafeteria",
        "date_reported": "2026-11-08",
    }
    data.update(overrides)
    return data


def test_home_lists_posts_and_links_to_details(client, app, test_db):
    assert b"No posts yet." in client.get("/").data

    user_id = _account(client, app)
    client.post("/auth/logout")
    first = _item(test_db, user_id, title="Blue backpack", date_reported=date(2026, 1, 1))
    second = _item(test_db, user_id, title="Silver laptop", listing_type="found",
                   category="electronics", date_reported=date(2026, 6, 1))

    page = client.get("/").data
    assert b"Blue backpack" in page
    assert b"Silver laptop" in page
    assert b"Lost" in page
    assert b"Found" in page
    assert b"bags" in page
    assert b"electronics" in page
    assert b"2026-01-01" in page
    assert b"2026-06-01" in page
    assert f'/items/{first.id}'.encode() in page
    assert f'/items/{second.id}'.encode() in page
    assert page.find(b"Silver laptop") < page.find(b"Blue backpack")
    assert b"student@example.edu" not in page

    listing = client.get("/posts/")
    assert listing.status_code == 200
    assert listing.is_json
    assert {post["title"] for post in listing.get_json()["posts"]} == {
        "Blue backpack", "Silver laptop",
    }


def test_search_filter_and_sort(client, app, test_db):
    user_id = _account(client, app)
    client.post("/auth/logout")
    _item(test_db, user_id, title="Blue backpack", description="Lost near the library",
          category="bags", listing_type="lost", date_reported=date(2026, 1, 1))
    _item(test_db, user_id, title="Silver laptop", description="Found in the lab",
          category="electronics", listing_type="found", date_reported=date(2026, 6, 1))

    keyword = client.get("/?q=LIBRARY").data
    assert b"Blue backpack" in keyword
    assert b"Silver laptop" not in keyword
    assert b">Clear</a>" in keyword

    lost = client.get("/?listing_type=lost").data
    assert b"Blue backpack" in lost
    assert b"Silver laptop" not in lost

    bags = client.get("/?category=bags").data
    assert b"Blue backpack" in bags
    assert b"Silver laptop" not in bags

    none = client.get("/?q=umbrella").data
    assert b"No matching posts." in none

    oldest = client.get("/?sort=oldest").data
    assert oldest.find(b"Blue backpack") < oldest.find(b"Silver laptop")

    cleared = client.get("/").data
    assert b"Blue backpack" in cleared
    assert b"Silver laptop" in cleared

    assert client.get("/posts/?listing_type=other").status_code == 400


def test_detail_page_shows_fields_and_unknown_id_is_404(client, app, test_db, monkeypatch):
    user_id = _account(client, app)
    client.post("/auth/logout")
    item = _item(test_db, user_id)
    item.photo_key = "items/" + "ab" * 16 + ".jpg"
    test_db.session.commit()
    monkeypatch.setattr(
        "app.items.routes.photo_url",
        lambda key: "https://photos.example/backpack.jpg",
    )

    page = client.get(f"/items/{item.id}")
    assert page.status_code == 200
    body = page.data
    assert b"Blue backpack" in body
    assert b"Lost near the library" in body
    assert b"bags" in body
    assert b"2026-01-02" in body
    assert b"Library" in body
    assert b"Lost" in body
    assert b"Open" in body
    assert b"https://photos.example/backpack.jpg" in body
    assert b"student@example.edu" not in body
    assert b"Edit" not in body

    missing = client.get("/items/9999")
    assert missing.status_code == 404
    assert b"Page not found" in missing.data
    assert b"Lost and Found" in missing.data

    api = client.get(f"/posts/{item.id}")
    assert api.status_code == 200
    assert api.is_json
    assert api.get_json()["title"] == "Blue backpack"


def test_create_post_requires_login_and_valid_fields(client, app, test_db):
    guest = client.get("/items/new")
    assert guest.status_code == 302
    assert "/auth/login" in guest.headers["Location"]

    register(client)
    empty = client.post("/items/new", data=_form(title="  "))
    assert empty.status_code == 200
    assert b"This field is required." in empty.data
    with app.app_context():
        from app.extensions import db
        assert db.session.execute(db.select(Item)).first() is None

    created = client.post("/items/new", data=_form())
    assert created.status_code == 302
    detail = client.get(created.headers["Location"])
    assert b"Lost wallet" in detail.data
    assert b"Black leather wallet" in detail.data
    assert b"Cafeteria" in detail.data
    home = client.get("/")
    assert b"Lost wallet" in home.data


def test_owner_can_edit_and_delete_and_others_cannot(client, app, test_db):
    owner_id = _account(client, app, email="owner@example.edu")
    item = _item(test_db, owner_id, title="Blue backpack")

    owner_page = client.get(f"/items/{item.id}")
    assert b"Edit" in owner_page.data
    assert b"Delete post" in owner_page.data

    edited = client.post(f"/items/{item.id}/edit", data=_form(title="Navy backpack"))
    assert edited.status_code == 302
    assert b"Navy backpack" in client.get(f"/items/{item.id}").data

    client.post("/auth/logout")
    register(client, email="other@example.edu")
    forbidden = client.get(f"/items/{item.id}")
    assert b"Edit" not in forbidden.data
    assert b"Delete post" not in forbidden.data
    assert b"Mark resolved" not in forbidden.data
    assert client.post(f"/items/{item.id}/edit", data=_form(title="Hijack")).status_code == 403
    assert client.post(f"/items/{item.id}/delete").status_code == 403
    assert client.post(f"/items/{item.id}/resolve").status_code == 403
    with app.app_context():
        from app.extensions import db
        assert db.session.get(Item, item.id).title == "Navy backpack"

    client.post("/auth/logout")
    login(client, email="owner@example.edu", password=GOOD_PASSWORD)
    deleted = client.post(f"/items/{item.id}/delete")
    assert deleted.status_code == 302
    assert deleted.headers["Location"].endswith("/")
    assert client.get(f"/items/{item.id}").status_code == 404
    assert b"Navy backpack" not in client.get("/").data


def test_owner_can_mark_a_post_resolved(client, app, test_db):
    owner_id = _account(client, app, email="owner@example.edu")
    item = _item(test_db, owner_id)

    page = client.get(f"/items/{item.id}")
    assert b"Mark resolved" in page.data
    assert b"Open" in page.data

    resolved = client.post(f"/items/{item.id}/resolve")
    assert resolved.status_code == 302
    detail = client.get(f"/items/{item.id}").data
    assert b"Resolved" in detail
    assert b"Mark resolved" not in detail
    assert b"Resolved" in client.get("/").data

    with app.app_context():
        from app.extensions import db
        assert db.session.get(Item, item.id).resolved is True


def test_non_image_upload_is_rejected_and_jpeg_waits_for_processing(client, app):
    register(client)

    rejected = client.post("/items/new", data={
        **_form(title="Text file"),
        "photo": (BytesIO(b"not a picture"), "notes.txt"),
    })
    assert rejected.status_code == 200
    assert b"Please choose an image file." in rejected.data
    with app.app_context():
        from app.extensions import db
        assert db.session.execute(db.select(Item)).first() is None

    accepted = client.post("/items/new", data={
        **_form(title="Camera photo"),
        "photo": (BytesIO(JPEG), "camera.jpg"),
    })
    assert accepted.status_code == 302
    with app.app_context():
        from app.extensions import db
        item = db.session.execute(db.select(Item)).scalar_one()
        assert item.title == "Camera photo"
        assert item.photo_key is None
    assert b"image processing" in client.get(accepted.headers["Location"]).data
