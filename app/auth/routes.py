"""Account sign-up, login, and logout (Part D)."""

from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth.forms import LoginForm, LogoutForm, RegistrationForm
from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Checked when an email doesn't exist so a missing account takes as long as a
# wrong password. Otherwise response timing would reveal which emails are registered.
_DUMMY_HASH = generate_password_hash("timing-equalizer-not-a-real-password")

LOGIN_FAILED = "Invalid email or password."


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
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.email.errors.append("An account with that email already exists.")
        else:
            _start_session(user)
            flash("Account created. Welcome!", "success")
            return redirect(url_for("index"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
        if user is None:
            check_password_hash(_DUMMY_HASH, form.password.data)
        elif user.check_password(form.password.data):
            _start_session(user, remember=form.remember.data)
            return redirect(_safe_next(request.args.get("next")) or url_for("index"))
        # Same message whether the email or the password was wrong.
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
