"""Private claim forms, submission, and poster-only review. No messaging here."""

import hashlib
import json

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.claims.forms import ClaimForm, QuestionsForm, ReviewForm
from app.extensions import db
from app.models import Claim, Item, Notification

claims_bp = Blueprint("claims", __name__)


@claims_bp.errorhandler(IntegrityError)
def claim_conflict(_error):
    db.session.rollback()
    return "Another claim changed this item. Refresh the page and try again.", 409


@claims_bp.errorhandler(SQLAlchemyError)
def database_error(_error):
    db.session.rollback()
    # SQL exception parameters can contain private answers; do not log them.
    current_app.logger.error("A claims database operation failed.")
    return "Claims are temporarily unavailable. Please try again later.", 503


def item_or_404(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        abort(404)
    return item


def claim_exists(item_id, status=None):
    query = db.select(Claim.id).where(Claim.item_id == item_id)
    if status is not None:
        query = query.where(Claim.status == status)
    return db.session.scalar(query.limit(1)) is not None


@claims_bp.route("/posts/<int:item_id>/ownership-questions", methods=["GET", "POST"])
@login_required
def questions(item_id):
    item = item_or_404(item_id)
    if item.user_id != current_user.id:
        abort(403)
    if item.listing_type != "found":
        abort(409, description="Ownership questions are only for found-item posts.")

    locked = claim_exists(item.id) or item.resolved
    form = QuestionsForm(data={"questions": item.ownership_questions or []}) if request.method == "GET" else QuestionsForm()
    if request.method == "POST" and locked:
        abort(409, description="Questions cannot change after a claim is submitted or the item is resolved.")
    if form.validate_on_submit():
        questions = [entry.data for entry in form.questions if entry.data]
        # Check and write together: a concurrent first claim must freeze the questions.
        result = db.session.execute(db.update(Item).where(
            Item.id == item.id, Item.user_id == current_user.id,
            Item.listing_type == "found", Item.resolved.is_(False),
            ~db.exists().where(Claim.item_id == item.id),
        ).values(ownership_questions=questions).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            db.session.rollback()
            abort(409, description="The item changed. Refresh before editing its questions.")
        db.session.commit()
        flash("Ownership questions saved.", "success")
        return redirect(url_for("post_pages.detail", post_id=item.id), code=303)
    return render_template("claims/questions.html", item=item, form=form, locked=locked), (400 if request.method == "POST" else 200)


@claims_bp.route("/posts/<int:item_id>/claims/new", methods=["GET", "POST"])
@login_required
def submit(item_id):
    item = item_or_404(item_id)
    if item.user_id == current_user.id:
        abort(403, description="You cannot claim your own item.")
    if item.listing_type != "found" or item.resolved or claim_exists(item.id, "approved"):
        abort(409, description="This item is not accepting claims.")
    questions = item.ownership_questions or []
    if not questions:
        abort(409, description="The poster has not added ownership questions yet.")
    pending = db.session.scalar(db.select(Claim.id).where(
        Claim.item_id == item.id, Claim.claimant_id == current_user.id, Claim.status == "pending",
    ).limit(1))
    if pending is not None:
        abort(409, description="You already have a pending claim. Check My claims for its status.")

    # Detect a form opened before the poster edited their questions. This is a
    # change fingerprint, not authentication; CSRF protection is supplied by Flask-WTF.
    version = hashlib.sha256(json.dumps(questions, ensure_ascii=False).encode()).hexdigest()
    form = ClaimForm(data={"answers": [""] * len(questions), "questions_version": version}) if request.method == "GET" else ClaimForm()
    form.expected_answers = len(questions)
    if request.method == "POST" and form.questions_version.data != version:
        abort(409, description="The ownership questions changed. Reload the form and answer the updated questions.")
    if form.validate_on_submit():
        # A conditional no-op UPDATE acquires SQLite's write lock while checking
        # the item is still open and its questions match the ones being answered.
        result = db.session.execute(db.update(Item).where(
            Item.id == item.id, Item.user_id != current_user.id,
            Item.listing_type == "found", Item.resolved.is_(False),
            Item.ownership_questions == questions,
            ~db.exists().where(Claim.item_id == item.id, Claim.status == "approved"),
        ).values(ownership_questions=questions).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            db.session.rollback()
            abort(409, description="This item changed and is no longer accepting this claim. Reload its page.")
        claim = Claim(
            item_id=item.id, claimant_id=current_user.id,
            ownership_answers=[{"question": question, "answer": answer.data}
                               for question, answer in zip(questions, form.answers)],
            supporting_details=form.supporting_details.data or None,
        )
        db.session.add(claim)
        db.session.add(Notification(user_id=item.user_id, type="claim_submitted", claim=claim))
        db.session.commit()
        flash("Your claim has been submitted for review.", "success")
        return redirect(url_for("claims.mine"), code=303)
    while len(form.answers) < len(questions):
        form.answers.append_entry()
    return render_template("claims/submit.html", item=item, form=form,
                           answer_fields=list(zip(questions, form.answers))), (400 if request.method == "POST" else 200)


@claims_bp.get("/posts/<int:item_id>/claims")
@login_required
def received(item_id):
    item = item_or_404(item_id)
    if item.user_id != current_user.id:
        abort(403)
    pagination = db.paginate(db.select(Claim).where(Claim.item_id == item.id)
                            .order_by(Claim.created_at.desc(), Claim.id.desc()),
                            per_page=20, max_per_page=20, error_out=False)
    can_approve = item.listing_type == "found" and not item.resolved and not claim_exists(item.id, "approved")
    return render_template("claims/received.html", item=item, pagination=pagination,
                           form=ReviewForm(), can_approve=can_approve)


@claims_bp.get("/claims/mine")
@login_required
def mine():
    pagination = db.paginate(db.select(Claim).where(Claim.claimant_id == current_user.id)
                            .order_by(Claim.created_at.desc(), Claim.id.desc()),
                            per_page=20, max_per_page=20, error_out=False)
    return render_template("claims/mine.html", pagination=pagination)


@claims_bp.post("/claims/<int:claim_id>/review")
@login_required
def review(claim_id):
    claim = db.session.get(Claim, claim_id)
    if claim is None:
        abort(404)
    item = claim.item
    if item.user_id != current_user.id:
        abort(403)
    form = ReviewForm()
    if not form.validate_on_submit():
        abort(400, description="Choose Approve or Deny.")
    if claim.status != "pending":
        abort(409, description="This claim has already been reviewed.")
    if form.decision.data == "approved":
        if claim_exists(item.id, "approved"):
            abort(409, description="Another claim has already been approved for this item.")
        result = db.session.execute(db.update(Item).where(
            Item.id == item.id, Item.user_id == current_user.id,
            Item.listing_type == "found", Item.resolved.is_(False),
        ).values(ownership_questions=item.ownership_questions))
        if result.rowcount != 1:
            db.session.rollback()
            abort(409, description="Only an unresolved found item can have a claim approved.")
    # The pending predicate prevents a second request from changing a final decision.
    result = db.session.execute(db.update(Claim).where(
        Claim.id == claim.id, Claim.status == "pending",
    ).values(status=form.decision.data))
    if result.rowcount != 1:
        db.session.rollback()
        abort(409, description="This claim has already been reviewed.")
    db.session.add(Notification(user_id=claim.claimant_id,
                                type=f"claim_{form.decision.data}", claim=claim))
    db.session.commit()
    flash("Claim approved." if form.decision.data == "approved" else "Claim denied.", "success")
    return redirect(url_for("claims.received", item_id=item.id), code=303)


@claims_bp.get("/claims/<int:claim_id>")
@login_required
def detail(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    if current_user.id not in (claim.claimant_id, claim.item.user_id):
        abort(404)
    is_poster = current_user.id == claim.item.user_id
    can_approve = (claim.item.listing_type == "found" and not claim.item.resolved
                   and not claim_exists(claim.item_id, "approved"))
    return render_template("claims/detail.html", claim=claim, is_poster=is_poster,
                           can_approve=can_approve, form=ReviewForm())
