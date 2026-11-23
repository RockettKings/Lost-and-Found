"""Requirements 5e and 5f: predict() and the post form's category prefill.

Most of these fake predict(), the way the Req 5 plan describes: a high guess, a
low guess, and a failure. The tests that need real weights skip when the
checkpoint is absent, so teammates without best_weights.pt still get a green run.
"""

import io

import pytest
from PIL import Image

from app import model as model_module
from app.categories import CATEGORIES


GOOD_PASSWORD = "correct-horse-battery"


def _jpeg_bytes(colour="blue", size=(64, 64)):
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="JPEG")
    return buffer.getvalue()


def _account(client, email="guesser@example.edu"):
    client.post("/auth/register", data={
        "username": email.split("@")[0], "email": email, "password": GOOD_PASSWORD, "confirm": GOOD_PASSWORD,
    }, follow_redirects=True)


def _upload(client, data=None):
    payload = {"photo": (io.BytesIO(_jpeg_bytes()), "item.jpg")}
    payload.update(data or {})
    return client.post("/api/posts/category-guess", data=payload,
                       content_type="multipart/form-data")


# --- 5e: predict() ----------------------------------------------------------

def test_unreadable_input_returns_no_category_instead_of_raising():
    assert model_module.predict(b"this is not an image") == (None, 0.0)
    assert model_module.predict(b"") == (None, 0.0)


def test_missing_weights_file_degrades_to_no_guess(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_WEIGHTS_PATH", str(tmp_path / "absent.pt"))
    monkeypatch.setattr(model_module, "_model", None)
    # A real JPEG, but nothing to load: still no exception.
    assert model_module.predict(_jpeg_bytes()) == (None, 0.0)


def test_labels_match_the_app_category_list():
    """The model's index order must be the app's vocabulary, or 5f fills a
    category that app/posts/routes.py then rejects."""
    assert model_module.LABELS == sorted(CATEGORIES)
    assert set(model_module.LABELS) == CATEGORIES


@pytest.mark.parametrize("confidence,expected", [(0.95, "wallet"), (0.10, None)])
def test_guess_for_form_applies_the_threshold(monkeypatch, confidence, expected):
    monkeypatch.setattr(model_module, "predict", lambda _bytes: ("wallet", confidence))
    category, reported = model_module.guess_for_form(b"ignored")
    assert category == expected
    assert reported == confidence


def test_threshold_is_in_range():
    assert 0.0 < model_module.CONFIDENCE_THRESHOLD < 1.0


@pytest.mark.skipif(not model_module.DEFAULT_WEIGHTS.exists(),
                    reason="best_weights.pt not present; train with cnn.py first")
def test_real_checkpoint_loads_and_predicts():
    """Guards against app/model.py's architecture drifting from cnn.py's."""
    category, confidence = model_module.predict(_jpeg_bytes())
    assert category in CATEGORIES
    assert 0.0 <= confidence <= 1.0


# --- 5f: the form endpoint --------------------------------------------------

def test_guess_endpoint_requires_login(client):
    assert _upload(client).status_code == 401


def test_guess_endpoint_returns_a_category_when_confident(client, app, monkeypatch):
    _account(client)
    monkeypatch.setattr("app.posts.guess.guess_for_form", lambda _b: ("wallet", 0.93))
    response = _upload(client)
    assert response.status_code == 200
    assert response.json == {"category": "wallet", "confidence": 0.93}


def test_low_confidence_leaves_the_category_blank(client, app, monkeypatch):
    _account(client)
    monkeypatch.setattr("app.posts.guess.guess_for_form", lambda _b: (None, 0.21))
    response = _upload(client)
    assert response.status_code == 200
    assert response.json["category"] is None


def test_model_failure_never_blocks_the_form(client, app, monkeypatch):
    """5f: a model failure leaves the field blank, it does not error the page."""
    def explode(_bytes):
        raise RuntimeError("model unavailable")

    _account(client)
    monkeypatch.setattr(model_module, "load_model", explode)
    monkeypatch.setattr(model_module, "_model", None)
    response = _upload(client)
    assert response.status_code == 200
    assert response.json["category"] is None


def test_non_image_upload_gets_no_guess_and_no_error(client, app):
    _account(client)
    response = client.post("/api/posts/category-guess", data={
        "photo": (io.BytesIO(b"not a picture"), "fake.jpg"),
    }, content_type="multipart/form-data")
    assert response.status_code == 200
    assert response.json["category"] is None


def test_missing_photo_field_is_not_an_error(client, app):
    _account(client)
    response = client.post("/api/posts/category-guess", data={},
                           content_type="multipart/form-data")
    assert response.status_code == 200
    assert response.json == {"category": None, "confidence": 0.0}


def test_guessed_category_is_only_a_suggestion(client, app, test_db, monkeypatch):
    """Requirement 11: whatever the guess was, the submitted category is saved."""
    _account(client)
    monkeypatch.setattr("app.posts.guess.guess_for_form", lambda _b: ("wallet", 0.99))
    assert _upload(client).json["category"] == "wallet"

    created = client.post("/api/posts/", json={
        "title": "Found keys", "description": "By the library door",
        "category": "keys", "listing_type": "found",
        "general_location": "Library", "date_reported": "2026-11-19",
    })
    assert created.status_code == 201
    assert created.json["post"]["category"] == "keys"
