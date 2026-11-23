"""Shared database models for accounts and lost/found posts."""

from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy.orm import validates
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


def utc_now():
    # SQLite stores timestamps without an offset; use UTC for every timestamp.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("length(email) BETWEEN 3 AND 254", name="email_length"),
        db.CheckConstraint("bio IS NULL OR length(bio) <= 500", name="bio_length"),
        db.Index("uq_users_username_lower", db.text("lower(username)"), unique=True),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    # The one public name. Stored as typed ("Nick_H") but unique ignoring case, so
    # nobody can register "nick_h" to imitate it; the database index enforces this.
    username = db.Column(db.String(20))
    # Migration 0003's display_name column is left in the table but unused: dropping it
    # needs a users rebuild, which SQLite refuses while items reference users.
    bio = db.Column(db.String(500), nullable=True)
    # D's account code supplies a Werkzeug hash, never a plaintext password.
    password_hash = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    # Only granted from the terminal (`flask make-admin`), never through a web form.
    is_admin = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("0"))
    items = db.relationship("Item", back_populates="user", passive_deletes="all")
    claims = db.relationship("Claim", back_populates="claimant", passive_deletes="all")

    @validates("email")
    def normalize_email(self, _field, email):
        return email.strip().lower()

    @property
    def display_name(self):
        # Accounts made before usernames existed are backfilled by migration 0008;
        # this fallback only covers rows inserted directly (e.g. in tests).
        return self.username or f"user{self.id}"

    # Older templates use this name; it never falls back to the email.
    public_name = display_name

    def set_password(self, password):
        # Werkzeug's default is salted scrypt; only the hash is ever stored.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    # Flask-Login stores only the user id in the signed session cookie.
    return db.session.get(User, int(user_id)) if user_id.isdigit() else None


class Item(db.Model):
    __tablename__ = "items"
    __table_args__ = (
        db.CheckConstraint("length(trim(title)) BETWEEN 1 AND 120", name="title_length"),
        db.CheckConstraint("length(trim(description)) BETWEEN 1 AND 2000", name="description_length"),
        db.CheckConstraint("length(trim(category)) BETWEEN 1 AND 80", name="category_length"),
        db.CheckConstraint("listing_type IN ('lost', 'found')", name="listing_type"),
        db.CheckConstraint("length(trim(general_location)) BETWEEN 1 AND 200", name="location_length"),
        db.CheckConstraint("photo_key IS NULL OR length(photo_key) BETWEEN 1 AND 255", name="photo_key_length"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"),
                        nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(2000), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    listing_type = db.Column(db.String(5), nullable=False)  # "lost" or "found"
    general_location = db.Column(db.String(200), nullable=False)
    date_reported = db.Column(db.Date, default=lambda: utc_now().date(), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    resolved = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("0"))
    photo_key = db.Column(db.String(255))  # S3 object key, not the image or an expiring URL
    ownership_questions = db.Column(db.JSON(none_as_null=True), nullable=True)
    user = db.relationship("User", back_populates="items")
    claims = db.relationship("Claim", back_populates="item", cascade="all, delete-orphan",
                             passive_deletes=True)


class Claim(db.Model):
    __tablename__ = "claims"
    __table_args__ = (
        db.CheckConstraint("status IN ('pending', 'approved', 'denied')", name="claim_status"),
        db.CheckConstraint("supporting_details IS NULL OR length(supporting_details) <= 2000",
                           name="claim_details_length"),
        # Partial indexes enforce these rules even if two requests arrive together.
        db.Index("uq_claim_pending_user_item", "item_id", "claimant_id", unique=True,
                 sqlite_where=db.text("status = 'pending'")),
        db.Index("uq_claim_approved_item", "item_id", unique=True,
                 sqlite_where=db.text("status = 'approved'")),
    )

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    claimant_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"),
                            nullable=False, index=True)
    # Keep the question text with each answer so its meaning survives future changes.
    ownership_answers = db.Column(db.JSON, nullable=False)
    supporting_details = db.Column(db.String(2000), nullable=True)
    status = db.Column(db.String(8), nullable=False, default="pending", server_default="pending")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    item = db.relationship("Item", back_populates="claims")
    claimant = db.relationship("User", back_populates="claims")


class Message(db.Model):
    __tablename__ = "messages"
    __table_args__ = (
        db.CheckConstraint("sender_id <> recipient_id", name="message_distinct_users"),
        db.CheckConstraint("length(trim(text)) BETWEEN 1 AND 2000", name="message_text_length"),
    )

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"),
                             nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="SET NULL"), nullable=True)
    text = db.Column(db.String(2000), nullable=False)
    sent_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    sender = db.relationship("User", foreign_keys=[sender_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])
    item = db.relationship("Item")


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (
        db.CheckConstraint(
            "(type = 'message' AND message_id IS NOT NULL AND claim_id IS NULL) OR "
            "(type IN ('claim_submitted', 'claim_approved', 'claim_denied') "
            "AND claim_id IS NOT NULL AND message_id IS NULL)",
            name="notification_target",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claims.id", ondelete="CASCADE"))
    message_id = db.Column(db.Integer, db.ForeignKey("messages.id", ondelete="CASCADE"))
    type = db.Column(db.String(20), nullable=False)
    read = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    claim = db.relationship("Claim")
    message = db.relationship("Message")
