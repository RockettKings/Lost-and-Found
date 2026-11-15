"""Requirements 32/33: claims, authorization, privacy, and existing-post integration."""

import re

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash
from flask_migrate import downgrade, upgrade

from app import create_app
from app.extensions import db
from app.models import Claim, Item, User
from tests.conftest import MIGRATIONS

PASSWORD = "claims test password"
QUESTION = "What is inside the front pocket?"
ANSWER = "Private identifying detail: ZEBRA calculator"


@pytest.fixture
def found_item(test_db):
    password_hash = generate_password_hash(PASSWORD)
    users = [User(email=f"{name}@example.edu", password_hash=password_hash)
             for name in ("owner", "claimant", "other")]
    item = Item(user=users[0], title="Found backpack", description="Found near library",
                category="bags", listing_type="found", general_location="Library",
                ownership_questions=[QUESTION])
    test_db.session.add_all([*users, item])
    test_db.session.commit()
    return item


def sign_in(client, name):
    client.post("/auth/logout")
    response = client.post("/auth/login", data={"email": f"{name}@example.edu", "password": PASSWORD})
    assert response.status_code == 302


def claim_data(client, target_id, answers=None, **extra):
    page = client.get(f"/posts/{target_id}/claims/new")
    assert page.status_code == 200
    version = re.search(r'name="questions_version"[^>]*value="([^"]+)"',
                        page.get_data(as_text=True)).group(1)
    values = {"questions_version": version, "supporting_details": "I can identify this item."}
    for index, answer in enumerate([ANSWER] if answers is None else answers):
        values[f"answers-{index}"] = answer
    values.update(extra)
    return values


def submit(client, item_id):
    response = client.post(f"/posts/{item_id}/claims/new", data=claim_data(client, item_id))
    assert response.status_code == 303
    return response


def test_owner_can_set_questions_and_claimant_sees_them(client, test_db, found_item):
    item_id = found_item.id
    sign_in(client, "owner")
    saved = client.post(f"/posts/{item_id}/ownership-questions", data={
        "questions-0": "  Describe a hidden mark.  ", "questions-1": "What is inside?", "questions-2": "",
    })
    assert saved.status_code == 303
    test_db.session.expire_all()
    assert found_item.ownership_questions == ["Describe a hidden mark.", "What is inside?"]
    sign_in(client, "claimant")
    form = client.get(f"/posts/{item_id}/claims/new")
    assert b"Describe a hidden mark." in form.data and b"What is inside?" in form.data
    assert b'name="answers-0"' in form.data and b'name="answers-1"' in form.data


@pytest.mark.parametrize("data", [{}, {"questions-0": "   "}, {"questions-0": "x" * 201},
                                  {f"questions-{i}": "Question" for i in range(4)}])
def test_invalid_questions_are_not_saved(client, test_db, found_item, data):
    sign_in(client, "owner")
    response = client.post(f"/posts/{found_item.id}/ownership-questions", data=data)
    assert response.status_code == 400
    test_db.session.expire_all()
    assert found_item.ownership_questions == [QUESTION]


def test_submission_saves_private_answers_and_server_owned_fields(client, test_db, found_item):
    sign_in(client, "claimant")
    data = claim_data(client, found_item.id, status="approved", claimant_id="1", item_id="999")
    response = client.post(f"/posts/{found_item.id}/claims/new", data=data)
    assert response.status_code == 303
    claim = test_db.session.execute(test_db.select(Claim)).scalar_one()
    assert claim.claimant.email == "claimant@example.edu"
    assert claim.item_id == found_item.id and claim.status == "pending"
    assert claim.ownership_answers == [{"question": QUESTION, "answer": ANSWER}]
    assert claim.supporting_details == "I can identify this item."
    assert claim.created_at is not None


@pytest.mark.parametrize("answers,details", [([], ""), ([" "], ""), (["x" * 1001], ""),
                                            ([ANSWER], "x" * 2001), ([ANSWER, "Extra"], "")])
def test_invalid_answers_do_not_create_claims(client, test_db, found_item, answers, details):
    sign_in(client, "claimant")
    data = claim_data(client, found_item.id, answers=answers, supporting_details=details)
    response = client.post(f"/posts/{found_item.id}/claims/new", data=data)
    assert response.status_code == 400
    assert test_db.session.execute(test_db.select(Claim)).first() is None


def test_owner_cannot_claim_and_others_cannot_set_questions(client, found_item):
    sign_in(client, "owner")
    assert client.get(f"/posts/{found_item.id}/claims/new").status_code == 403
    assert client.post(f"/posts/{found_item.id}/claims/new", data={}).status_code == 403
    sign_in(client, "claimant")
    assert client.get(f"/posts/{found_item.id}/ownership-questions").status_code == 403
    assert client.post(f"/posts/{found_item.id}/ownership-questions", data={"questions-0": "Hijacked"}).status_code == 403


@pytest.mark.parametrize("path,method", [
    ("/posts/1/ownership-questions", "get"), ("/posts/1/ownership-questions", "post"),
    ("/posts/1/claims/new", "get"), ("/posts/1/claims/new", "post"),
    ("/posts/1/claims", "get"), ("/claims/mine", "get"), ("/claims/1/review", "post"),
])
def test_all_claim_routes_require_login(client, path, method):
    response = getattr(client, method)(path)
    assert response.status_code == 302 and "/auth/login" in response.headers["Location"]


@pytest.mark.parametrize("changes", [{"listing_type": "lost"}, {"resolved": True}, {"ownership_questions": None}])
def test_claims_require_open_found_item_with_questions(client, test_db, found_item, changes):
    for name, value in changes.items():
        setattr(found_item, name, value)
    test_db.session.commit()
    sign_in(client, "claimant")
    assert client.get(f"/posts/{found_item.id}/claims/new").status_code == 409
    assert client.post(f"/posts/{found_item.id}/claims/new", data={}).status_code == 409


def test_duplicate_pending_claim_is_refused_but_denied_user_can_resubmit(client, test_db, found_item):
    sign_in(client, "claimant")
    data = claim_data(client, found_item.id)
    assert client.post(f"/posts/{found_item.id}/claims/new", data=data).status_code == 303
    assert client.post(f"/posts/{found_item.id}/claims/new", data=data).status_code == 409
    claim = test_db.session.execute(test_db.select(Claim)).scalar_one()
    sign_in(client, "owner")
    assert client.post(f"/claims/{claim.id}/review", data={"decision": "denied"}).status_code == 303
    sign_in(client, "claimant")
    submit(client, found_item.id)
    statuses = test_db.session.execute(test_db.select(Claim.status).order_by(Claim.id)).scalars().all()
    assert statuses == ["denied", "pending"]


def test_questions_freeze_after_claim_and_old_forms_cannot_answer_changed_questions(client, test_db, found_item):
    sign_in(client, "claimant")
    old_data = claim_data(client, found_item.id)
    sign_in(client, "owner")
    assert client.post(f"/posts/{found_item.id}/ownership-questions",
                       data={"questions-0": "What is the serial number?"}).status_code == 303
    sign_in(client, "claimant")
    assert client.post(f"/posts/{found_item.id}/claims/new", data=old_data).status_code == 409
    submit(client, found_item.id)
    sign_in(client, "owner")
    locked = client.get(f"/posts/{found_item.id}/ownership-questions")
    assert locked.status_code == 200 and b"Questions are locked" in locked.data
    assert client.post(f"/posts/{found_item.id}/ownership-questions",
                       data={"questions-0": "Replacement"}).status_code == 409


@pytest.mark.parametrize("decision", ["approved", "denied"])
def test_poster_can_review_and_claimant_sees_result(client, test_db, found_item, decision):
    sign_in(client, "claimant")
    submit(client, found_item.id)
    claim = test_db.session.execute(test_db.select(Claim)).scalar_one()
    sign_in(client, "owner")
    inbox = client.get(f"/posts/{found_item.id}/claims")
    assert ANSWER.encode() in inbox.data and QUESTION.encode() in inbox.data
    assert client.post(f"/claims/{claim.id}/review", data={"decision": decision}).status_code == 303
    test_db.session.expire_all()
    assert claim.status == decision
    assert found_item.resolved is False  # Resolution remains Khang's workflow.
    assert client.post(f"/claims/{claim.id}/review", data={"decision": "denied"}).status_code == 409
    sign_in(client, "claimant")
    status_page = client.get("/claims/mine")
    assert decision.capitalize().encode() in status_page.data and ANSWER.encode() in status_page.data


def test_claims_are_private_and_third_party_cannot_review(client, test_db, found_item):
    sign_in(client, "claimant")
    submit(client, found_item.id)
    claim = test_db.session.execute(test_db.select(Claim)).scalar_one()
    assert client.get(f"/posts/{found_item.id}/claims").status_code == 403
    assert client.post(f"/claims/{claim.id}/review", data={"decision": "approved"}).status_code == 403
    sign_in(client, "other")
    assert client.get(f"/posts/{found_item.id}/claims").status_code == 403
    assert client.post(f"/claims/{claim.id}/review", data={"decision": "approved"}).status_code == 403
    assert ANSWER.encode() not in client.get("/claims/mine?claimant_id=2").data
    client.post("/auth/logout")
    for path in ("/", f"/posts/{found_item.id}", "/api/posts/", f"/api/posts/{found_item.id}"):
        assert ANSWER.encode() not in client.get(path).data
    test_db.session.expire_all()
    assert claim.status == "pending"


def test_only_one_claim_can_be_approved_and_new_claims_then_close(client, test_db, found_item):
    for name in ("claimant", "other"):
        sign_in(client, name)
        submit(client, found_item.id)
    claims = test_db.session.execute(test_db.select(Claim).order_by(Claim.id)).scalars().all()
    sign_in(client, "owner")
    assert client.post(f"/claims/{claims[0].id}/review", data={"decision": "approved"}).status_code == 303
    assert client.post(f"/claims/{claims[1].id}/review", data={"decision": "approved"}).status_code == 409
    test_db.session.expire_all()
    assert [claim.status for claim in claims] == ["approved", "pending"]
    sign_in(client, "other")
    assert client.get(f"/posts/{found_item.id}/claims/new").status_code == 409


def test_closed_item_cannot_be_approved_and_invalid_decisions_are_refused(client, test_db, found_item):
    sign_in(client, "claimant")
    submit(client, found_item.id)
    claim = test_db.session.execute(test_db.select(Claim)).scalar_one()
    found_item.resolved = True
    test_db.session.commit()
    sign_in(client, "owner")
    assert client.post(f"/claims/{claim.id}/review", data={"decision": "approved"}).status_code == 409
    assert client.post(f"/claims/{claim.id}/review", data={"decision": "pending"}).status_code == 400
    assert client.get(f"/claims/{claim.id}/review").status_code == 405


def test_claimed_posts_cannot_change_to_lost_but_can_still_be_deleted(client, test_db, found_item):
    item_id = found_item.id
    sign_in(client, "claimant")
    submit(client, item_id)
    sign_in(client, "owner")
    assert client.patch(f"/api/posts/{item_id}", json={"listing_type": "lost"}).status_code == 409
    assert client.patch(f"/api/posts/{item_id}", json={"title": "Updated backpack"}).status_code == 200
    assert client.delete(f"/api/posts/{item_id}").status_code == 204
    assert test_db.session.execute(test_db.select(Claim)).first() is None
    assert test_db.session.execute(text("PRAGMA foreign_key_check")).all() == []


def test_database_prevents_duplicate_pending_claims_without_route_checks(test_db, found_item):
    claimant_id = test_db.session.scalar(test_db.select(User.id).where(User.email == "claimant@example.edu"))
    values = {"item_id": found_item.id, "claimant_id": claimant_id,
              "ownership_answers": [{"question": QUESTION, "answer": ANSWER}]}
    test_db.session.add(Claim(**values))
    test_db.session.commit()
    test_db.session.add(Claim(**values))
    with pytest.raises(IntegrityError):
        test_db.session.commit()
    test_db.session.rollback()


def test_claims_csrf_and_escaped_answers(client, app, test_db, found_item):
    sign_in(client, "claimant")
    app.config["WTF_CSRF_ENABLED"] = True
    data = claim_data(client, found_item.id, answers=["<script>alert('private')</script>"])
    assert client.post(f"/posts/{found_item.id}/claims/new", data=data).status_code == 400
    page = client.get(f"/posts/{found_item.id}/claims/new").get_data(as_text=True)
    data["csrf_token"] = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page).group(1)
    assert client.post(f"/posts/{found_item.id}/claims/new", data=data).status_code == 303
    own = client.get("/claims/mine")
    assert b"<script>alert" not in own.data and b"&lt;script&gt;" in own.data


def test_three_questions_and_maximum_answer_lengths(client, test_db, found_item):
    sign_in(client, "owner")
    questions = {f"questions-{i}": str(i) + "q" * 199 for i in range(3)}
    assert client.post(f"/posts/{found_item.id}/ownership-questions", data=questions).status_code == 303
    sign_in(client, "claimant")
    data = claim_data(client, found_item.id, answers=["a" * 1000] * 3, supporting_details="d" * 2000)
    assert client.post(f"/posts/{found_item.id}/claims/new", data=data).status_code == 303
    claim = test_db.session.execute(test_db.select(Claim)).scalar_one()
    assert len(claim.ownership_answers) == 3
    assert all(len(entry["question"]) == 200 and len(entry["answer"]) == 1000
               for entry in claim.ownership_answers)
    assert len(claim.supporting_details) == 2000


def test_database_prevents_multiple_approvals(test_db, found_item):
    claimant_ids = test_db.session.execute(test_db.select(User.id).where(
        User.email != "owner@example.edu").order_by(User.id)).scalars().all()
    values = {"item_id": found_item.id, "ownership_answers": [], "status": "approved"}
    test_db.session.add(Claim(claimant_id=claimant_ids[0], **values))
    test_db.session.commit()
    test_db.session.add(Claim(claimant_id=claimant_ids[1], **values))
    with pytest.raises(IntegrityError):
        test_db.session.commit()
    test_db.session.rollback()


@pytest.mark.parametrize("invalid", [{"item_id": 9999}, {"claimant_id": 9999},
                                     {"status": "invalid"}, {"supporting_details": "d" * 2001}])
def test_database_rejects_invalid_claim_records(test_db, found_item, invalid):
    values = {"item_id": found_item.id, "claimant_id": 2, "ownership_answers": []}
    values.update(invalid)
    test_db.session.add(Claim(**values))
    with pytest.raises(IntegrityError):
        test_db.session.commit()
    test_db.session.rollback()


def test_question_and_review_posts_require_csrf(client, app, test_db, found_item):
    sign_in(client, "owner")
    app.config["WTF_CSRF_ENABLED"] = True
    path = f"/posts/{found_item.id}/ownership-questions"
    assert client.post(path, data={"questions-0": "New question"}).status_code == 400
    page = client.get(path).get_data(as_text=True)
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page).group(1)
    assert client.post(path, data={"questions-0": QUESTION, "csrf_token": token}).status_code == 303
    claim = Claim(item_id=found_item.id, claimant_id=2,
                  ownership_answers=[{"question": QUESTION, "answer": ANSWER}])
    test_db.session.add(claim)
    test_db.session.commit()
    review_path = f"/claims/{claim.id}/review"
    assert client.post(review_path, data={"decision": "approved"}).status_code == 400
    assert claim.status == "pending"
    page = client.get(f"/posts/{found_item.id}/claims").get_data(as_text=True)
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page).group(1)
    assert client.post(review_path, data={"decision": "approved", "csrf_token": token}).status_code == 303
    test_db.session.expire_all()
    assert claim.status == "approved"


def test_private_lists_are_paginated(client, test_db, found_item):
    test_db.session.add_all([Claim(item_id=found_item.id, claimant_id=2, status="denied",
                                   ownership_answers=[{"question": QUESTION, "answer": ANSWER}])
                             for _ in range(21)])
    test_db.session.commit()
    sign_in(client, "claimant")
    assert client.get("/claims/mine").data.count(ANSWER.encode()) == 20
    assert client.get("/claims/mine?page=2").data.count(ANSWER.encode()) == 1
    sign_in(client, "owner")
    assert client.get(f"/posts/{found_item.id}/claims").data.count(ANSWER.encode()) == 20
    assert client.get(f"/posts/{found_item.id}/claims?page=2").data.count(ANSWER.encode()) == 1


def test_claim_migration_preserves_existing_profiles_and_posts(tmp_path):
    application = create_app({
        "TESTING": True, "APP_ENV": "testing", "SECRET_KEY": "claims-migration-test",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'existing.sqlite3'}",
    })
    with application.app_context():
        upgrade(directory=MIGRATIONS, revision="0003")
        password_hash = generate_password_hash(PASSWORD)
        for user_id, email in ((1, "owner@example.edu"), (2, "claimant@example.edu")):
            db.session.execute(text(
                "INSERT INTO users (id, email, password_hash, created_at, display_name, bio) "
                "VALUES (:id, :email, :hash, '2026-11-01 12:00:00', :name, 'Student')"
            ), {"id": user_id, "email": email, "hash": password_hash, "name": f"Person {user_id}"})
        db.session.execute(text(
            "INSERT INTO items (id, user_id, title, description, category, listing_type, "
            "general_location, date_reported, created_at, resolved) "
            "VALUES (1, 1, 'Backpack', 'Blue bag', 'bags', 'found', 'Library', "
            "'2026-11-01', '2026-11-01 12:00:00', 0)"
        ))
        db.session.commit()
        db.session.remove()
        upgrade(directory=MIGRATIONS)
        item = db.session.get(Item, 1)
        assert item.ownership_questions is None and item.title == "Backpack"
        assert item.user.display_name == "Person 1" and item.user.bio == "Student"
        assert item.user.check_password(PASSWORD)
        db.session.add(Claim(item_id=1, claimant_id=2, ownership_answers=[]))
        db.session.commit()
        assert db.session.execute(text("PRAGMA foreign_key_check")).all() == []
        db.session.remove()
        downgrade(directory=MIGRATIONS, revision="0003")
        assert db.session.execute(text("SELECT title FROM items WHERE id = 1")).scalar_one() == "Backpack"
        assert db.session.execute(text("SELECT display_name FROM users WHERE id = 1")).scalar_one() == "Person 1"
        db.session.remove()
        upgrade(directory=MIGRATIONS)
        assert db.session.get(Item, 1).user.id == 1
        db.session.remove()
        db.engine.dispose()
