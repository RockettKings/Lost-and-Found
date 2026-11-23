"""Requirement 31: photos go to cloud storage, come back for display, and fail safely."""

from io import BytesIO
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from PIL import Image

from app import storage
from app.models import Item
from app.posts.photos import UPLOAD_FAILED
from tests.test_pages import _account, _form, _item

OLD_KEY = "items/" + "cd" * 16 + ".jpg"


def _jpeg():
    upload = BytesIO()
    Image.new("RGB", (12, 8), "red").save(upload, format="JPEG")
    upload.seek(0)
    return upload


@pytest.fixture
def s3(monkeypatch):
    client = Mock()
    client.generate_presigned_url.return_value = "https://bucket.example/signed"
    monkeypatch.setattr(storage.boto3, "client", Mock(return_value=client))
    return client


def test_get_photo_returns_a_signed_url_for_the_stored_key(app, s3):
    with app.app_context():
        assert storage.get_photo(OLD_KEY) == "https://bucket.example/signed"
    s3.generate_presigned_url.assert_called_once_with(
        "get_object", Params={"Bucket": "test-bucket", "Key": OLD_KEY}, ExpiresIn=900)


def test_detail_shows_the_photo_from_cloud_storage(client, app, test_db, s3):
    item = _item(test_db, _account(client, app), photo_key=OLD_KEY)
    assert client.get(f"/api/posts/{item.id}").json["post"]["photo_url"] == "https://bucket.example/signed"


def test_accepted_photo_is_uploaded_and_linked_to_the_post(client, app, test_db, s3):
    _account(client, app)
    created = client.post("/api/posts/", data={**_form(), "photo": (_jpeg(), "wallet.jpg")})
    assert created.status_code == 201
    saved = test_db.session.get(Item, created.json["post"]["id"])
    assert saved.photo_key.startswith("items/")
    assert s3.put_object.call_args.kwargs["Key"] == saved.photo_key


@pytest.mark.parametrize("failure", [
    ClientError({"Error": {"Code": "AccessDenied", "Message": "denied"}}, "PutObject"),
    EndpointConnectionError(endpoint_url="https://s3.example"),
])
def test_failed_upload_shows_an_error_and_saves_no_post(client, app, test_db, s3, failure):
    _account(client, app)
    s3.put_object.side_effect = failure
    response = client.post("/api/posts/", data={**_form(), "photo": (_jpeg(), "wallet.jpg")})
    assert response.status_code == 400
    assert response.json["errors"]["photo"] == UPLOAD_FAILED
    assert test_db.session.execute(test_db.select(Item)).first() is None


def test_missing_bucket_setting_shows_an_error_and_saves_no_post(client, app, test_db, s3):
    _account(client, app)
    app.config["S3_BUCKET"] = None
    response = client.post("/api/posts/", data={**_form(), "photo": (_jpeg(), "wallet.jpg")})
    assert response.status_code == 400
    assert response.json["errors"]["photo"] == UPLOAD_FAILED
    assert test_db.session.execute(test_db.select(Item)).first() is None
    s3.put_object.assert_not_called()


def test_failed_replacement_keeps_the_existing_photo(client, app, test_db, s3):
    item = _item(test_db, _account(client, app), photo_key=OLD_KEY)
    s3.put_object.side_effect = ClientError({"Error": {"Code": "SlowDown", "Message": "busy"}}, "PutObject")
    response = client.patch(f"/api/posts/{item.id}", data={"photo": (_jpeg(), "new.jpg")})
    assert response.status_code == 400
    assert response.json["errors"]["photo"] == UPLOAD_FAILED
    test_db.session.expire_all()
    assert test_db.session.get(Item, item.id).photo_key == OLD_KEY
    s3.delete_object.assert_not_called()
