"""Account sign-up, login, and logout (Part D)."""

from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth.forms import LoginForm, LogoutForm, RegistrationForm, UsernameForm
from app.extensions import db, limiter
from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Checked when an email doesn't exist so a missing account takes as long as a
# wrong password. Otherwise response timing would reveal which emails are registered.
_DUMMY_HASH = generate_password_hash("timing-equalizer-not-a-real-password")

LOGIN_FAILED = "Invalid email, username, or password."
EMAIL_TAKEN = "An account with that email already exists."
USERNAME_TAKEN = "That username is already taken."


def _registration_conflicts(email, username):
    """Return (email_taken, username_taken). Usernames are compared ignoring case."""
    email_taken = db.session.execute(
        db.select(User.id).filter_by(email=email.strip().lower())
    ).first() is not None
    username_taken = db.session.execute(
        db.select(User.id).where(func.lower(User.username) == username.lower())
    ).first() is not None
    return email_taken, username_taken


def _find_login_user(identifier):
    """Look up an account by email (contains "@") or by username, ignoring case."""
    identifier = identifier.strip()
    if "@" in identifier:
        statement = db.select(User).filter_by(email=identifier.lower())
    else:
        statement = db.select(User).where(func.lower(User.username) == identifier.lower())
    return db.session.execute(statement).scalar_one_or_none()


def _safe_next(target):
    """Only allow same-site relative paths, preventing open redirects like ?next=//evil.com."""
    if not target:
        return None
    target = target.replace("\\", "/")
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target


def _start_session(user, remember=False):
    # Drop all previous session data so a pre-login session can't be reused (session fixation).
    session.clear()
    login_user(user, remember=remember)
    session.permanent = True  # Applies PERMANENT_SESSION_LIFETIME as an idle timeout.


@auth_bp.route("/register", methods=["GET", "POST"])
# Slows mass account creation and probing which emails are registered.
@limiter.limit("5 per minute;20 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        email_taken, username_taken = _registration_conflicts(form.email.data, form.username.data)
        if email_taken:
            form.email.errors.append(EMAIL_TAKEN)
        if username_taken:
            form.username.errors.append(USERNAME_TAKEN)
        if email_taken or username_taken:
            return render_template("auth/register.html", form=form)

        user = User(email=form.email.data, username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            # Another sign-up claimed the email or username between the check and the insert.
            db.session.rollback()
            email_taken, username_taken = _registration_conflicts(form.email.data, form.username.data)
            if username_taken:
                form.username.errors.append(USERNAME_TAKEN)
            if email_taken or not username_taken:
                form.email.errors.append(EMAIL_TAKEN)
        else:
            _start_session(user)
            flash("Account created. Welcome!", "success")
            return redirect(url_for("index"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
# Stops password guessing: a handful of tries per minute per IP.
@limiter.limit("5 per minute;30 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = _find_login_user(form.identifier.data)
        if user is None:
            check_password_hash(_DUMMY_HASH, form.password.data)
        elif user.check_password(form.password.data):
            _start_session(user, remember=form.remember.data)
            return redirect(_safe_next(request.args.get("next")) or url_for("index"))
        # Same message whether the email/username or the password was wrong.
        flash(LOGIN_FAILED, "error")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    if LogoutForm().validate_on_submit():
        logout_user()
        session.clear()
        flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@auth_bp.route("/username", methods=["GET", "POST"])
@login_required
# Stops someone cycling names quickly (e.g. grabbing a name the moment it's freed).
@limiter.limit("5 per hour", methods=["POST"])
def change_username():
    form = UsernameForm()
    if request.method == "GET":
        form.username.data = current_user.username
    elif form.validate_on_submit():
        new_name = form.username.data
        if new_name == current_user.username:
            flash("That's already your username.", "info")
            return redirect(url_for("auth.change_username"))
        taken = db.session.execute(
            db.select(User.id).where(func.lower(User.username) == new_name.lower(),
                                     User.id != current_user.id)
        ).first() is not None
        if taken:
            form.username.errors.append(USERNAME_TAKEN)
        else:
            current_user.username = new_name
            try:
                db.session.commit()
            except IntegrityError:
                # Someone else claimed it between the check and the save.
                db.session.rollback()
                form.username.errors.append(USERNAME_TAKEN)
            else:
                flash(f"Your username is now @{new_name}.", "success")
                return redirect(url_for("index"))
    return render_template("auth/username.html", form=form)
