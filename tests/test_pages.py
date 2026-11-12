"""Page shells and their JSON data: Flask's client does not execute JavaScript."""

from datetime import date
from io import BytesIO
import re

from PIL import Image

from app.models import Item, User
from app.photo_pipeline.strip_metadata import has_gps
from tests.test_auth import GOOD_PASSWORD, login, register


def _account(client, app, email="student@example.edu"):
    register(client, email=email)
    with app.app_context():
        from app.extensions import db
        return db.session.execute(db.select(User).filter_by(email=email)).scalar_one().id


def _item(test_db, user_id, **overrides):
    fields = {
        "title": "Blue backpack", "description": "Lost near the library",
        "category": "bags", "listing_type": "lost", "general_location": "Library",
        "date_reported": date(2026, 1, 2),
    }
    fields.update(overrides)
    item = Item(user_id=user_id, **fields)
    test_db.session.add(item)
    test_db.session.commit()
    return item


def _form(title="Lost wallet", **overrides):
    data = {
        "title": title, "description": "Black leather wallet", "category": "Accessories",
        "listing_type": "lost", "general_location": "Cafeteria", "date_reported": "2026-11-08",
    }
    data.update(overrides)
    return data


def test_home_loads_assets_and_listing_data(client, app, test_db):
    page = client.get("/")
    assert page.status_code == 200
    assert b'id="post-list"' in page.data
    assert b'id="post-search-form"' in page.data
    # Every asset referenced by the layout must exist, including its JS data loader.
    assets = re.findall(r'(?:href|src)="(/static/[^\"]+)"', page.get_data(as_text=True))
    assert "/static/posts.js" in assets
    for asset in assets:
        assert client.get(asset).status_code == 200
    assert client.get("/api/posts/").json == {"posts": []}

    user_id = _account(client, app)
    client.post("/auth/logout")
    first = _item(test_db, user_id, date_reported=date(2026, 1, 1))
    second = _item(test_db, user_id, title="Silver laptop", listing_type="found",
                   category="electronics", date_reported=date(2026, 6, 1))
    listing = client.get("/api/posts/")
    assert listing.status_code == 200
    assert [post["id"] for post in listing.json["posts"]] == [second.id, first.id]
    assert {post["listing_type"] for post in listing.json["posts"]} == {"lost", "found"}
    assert {post["category"] for post in listing.json["posts"]} == {"bags", "electronics"}
    for post in listing.json["posts"]:
        assert client.get(f'/posts/{post["id"]}').status_code == 200
    assert b"student@example.edu" not in listing.data


def test_search_filter_and_sort(client, app, test_db):
    user_id = _account(client, app)
    client.post("/auth/logout")
    _item(test_db, user_id, date_reported=date(2026, 1, 1))
    _item(test_db, user_id, title="Silver laptop", description="Found in the lab",
          category="electronics", listing_type="found", date_reported=date(2026, 6, 1))

    def titles(query=""):
        response = client.get("/api/posts/" + query)
        assert response.status_code == 200
        return [post["title"] for post in response.json["posts"]]

    assert titles("?q=LIBRARY") == ["Blue backpack"]
    assert titles("?listing_type=lost") == ["Blue backpack"]
    assert titles("?category=bags") == ["Blue backpack"]
    assert titles("?q=LIBRARY&category=bags&listing_type=lost") == ["Blue backpack"]
    assert titles("?q=umbrella") == []
    assert titles("?sort=oldest") == ["Blue backpack", "Silver laptop"]
    assert titles() == ["Silver laptop", "Blue backpack"]
    assert client.get("/api/posts/?listing_type=other").status_code == 400


def test_detail_page_and_api_keep_private_fields_hidden(client, app, test_db, monkeypatch):
    user_id = _account(client, app)
    client.post("/auth/logout")
    item = _item(test_db, user_id, photo_key="items/" + "ab" * 16 + ".jpg")
    monkeypatch.setattr("app.posts.routes.photo_url", lambda key: "https://photos.example/backpack.jpg")

    page = client.get(f"/posts/{item.id}")
    assert page.status_code == 200
    assert f'data-post-id="{item.id}"'.encode() in page.data
    api = client.get(f"/api/posts/{item.id}")
    assert api.status_code == 200
    post = api.json["post"]
    assert post["title"] == "Blue backpack"
    assert post["description"] == "Lost near the library"
    assert post["category"] == "bags"
    assert post["date_reported"] == "2026-01-02"
    assert post["general_location"] == "Library"
    assert post["listing_type"] == "lost"
    assert post["resolved"] is False
    assert post["photo_url"] == "https://photos.example/backpack.jpg"
    assert post["is_owner"] is False
    assert "email" not in post and "password_hash" not in post and "user_id" not in post
    assert b"student@example.edu" not in page.data + api.data

    missing = client.get("/posts/9999")
    assert missing.status_code == 404
    assert b"Page not found" in missing.data
    assert b"Lost and Found" in missing.data
    missing_api = client.get("/api/posts/9999")
    assert missing_api.status_code == 404 and missing_api.is_json


def test_create_post_requires_login_and_valid_fields(client, app, test_db):
    guest = client.get("/posts/new")
    assert guest.status_code == 302
    assert "/auth/login" in guest.headers["Location"]
    assert client.post("/api/posts/", json=_form()).status_code == 401

    register(client)
    page = client.get("/posts/new")
    assert page.status_code == 200
    assert b'id="post-form"' in page.data
    empty = client.post("/api/posts/", data=_form(title="  "))
    assert empty.status_code == 400
    assert "title" in empty.json["errors"]
    assert test_db.session.execute(test_db.select(Item)).first() is None

    created = client.post("/api/posts/", data=_form())
    assert created.status_code == 201
    post = created.json["post"]
    assert post["title"] == "Lost wallet"
    assert post["description"] == "Black leather wallet"
    assert post["general_location"] == "Cafeteria"
    assert client.get(f'/posts/{post["id"]}').status_code == 200
    assert client.get("/api/posts/").json["posts"][0]["id"] == post["id"]


def test_owner_can_edit_and_delete_and_others_cannot(client, app, test_db):
    owner_id = _account(client, app, email="owner@example.edu")
    item = _item(test_db, owner_id)
    item_id = item.id
    assert client.get(f"/posts/{item_id}/edit").status_code == 200
    assert client.get(f"/api/posts/{item_id}").json["post"]["is_owner"] is True
    edited = client.patch(f"/api/posts/{item_id}", json={"title": "Navy backpack"})
    assert edited.status_code == 200
    assert edited.json["post"]["title"] == "Navy backpack"

    client.post("/auth/logout")
    register(client, email="other@example.edu")
    assert client.get(f"/api/posts/{item_id}").json["post"]["is_owner"] is False
    forbidden = client.get(f"/posts/{item_id}/edit")
    assert forbidden.status_code == 403
    assert b"Lost and Found" in forbidden.data and not forbidden.is_json
    assert client.patch(f"/api/posts/{item_id}", json={"title": "Hijack"}).status_code == 403
    assert client.delete(f"/api/posts/{item_id}").status_code == 403
    assert client.patch(f"/api/posts/{item_id}", json={"resolved": True}).status_code == 403
    test_db.session.expire_all()
    assert test_db.session.get(Item, item_id).title == "Navy backpack"

    client.post("/auth/logout")
    login(client, email="owner@example.edu", password=GOOD_PASSWORD)
    assert client.delete(f"/api/posts/{item_id}").status_code == 204
    assert client.get(f"/posts/{item_id}").status_code == 404
    assert client.get("/api/posts/").json == {"posts": []}
    test_db.session.expire_all()
    assert test_db.session.get(Item, item_id) is None


def test_owner_can_mark_a_post_resolved(client, app, test_db):
    owner_id = _account(client, app)
    item = _item(test_db, owner_id)
    resolved = client.patch(f"/api/posts/{item.id}", json={"resolved": True})
    assert resolved.status_code == 200
    assert resolved.json["post"]["resolved"] is True
    assert client.get(f"/api/posts/{item.id}").json["post"]["resolved"] is True
    assert client.get("/api/posts/").json["posts"][0]["resolved"] is True
    test_db.session.expire_all()
    assert test_db.session.get(Item, item.id).resolved is True


def test_non_image_is_rejected_and_photo_is_processed_before_storage(client, app, test_db, monkeypatch):
    register(client)
    stored = []
    key = "items/" + "ab" * 16 + ".jpg"

    def save_processed_photo(data):
        stored.append(data)
        with Image.open(BytesIO(data)) as image:
            assert image.format == "JPEG"
            assert not has_gps(image)
            assert image.size == (10, 20)  # Input orientation has been applied.
        return key

    # Fake only cloud storage; run the real image validation/metadata pipeline.
    monkeypatch.setattr("app.posts.photos.save_photo", save_processed_photo)
    monkeypatch.setattr("app.posts.routes.photo_url", lambda key: "https://photos.example/photo.jpg")
    rejected = client.post("/api/posts/", data={
        **_form(title="Text file"), "photo": (BytesIO(b"not a picture"), "fake.jpg"),
    })
    assert rejected.status_code == 400
    assert "photo" in rejected.json["errors"]
    assert not stored
    assert test_db.session.execute(test_db.select(Item)).first() is None

    image = Image.new("RGB", (20, 10), "blue")
    exif = Image.Exif()
    exif[274] = 6
    exif[34853] = {1: "N", 2: (10.0, 0.0, 0.0), 3: "E", 4: (20.0, 0.0, 0.0)}
    upload = BytesIO()
    image.save(upload, format="JPEG", exif=exif)
    upload.seek(0)
    assert has_gps(upload)
    upload.seek(0)
    accepted = client.post("/api/posts/", data={
        **_form(title="Camera photo"), "photo": (upload, "camera.jpg"),
    })
    assert accepted.status_code == 201
    assert len(stored) == 1
    saved = test_db.session.get(Item, accepted.json["post"]["id"])
    assert saved.photo_key == key
    assert accepted.json["post"]["photo_url"] == "https://photos.example/photo.jpg"
