"""Sprint 1 stores accounts and lost/found posts. Claims come in a later sprint."""

from datetime import datetime, timezone

from sqlalchemy.orm import validates

from app.extensions import db


def utc_now():
    # SQLite stores timestamps without an offset; use UTC for every timestamp.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("length(email) BETWEEN 3 AND 254", name="email_length"),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    # D's account code supplies a Werkzeug hash, never a plaintext password.
    password_hash = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    items = db.relationship("Item", back_populates="user", passive_deletes="all")

    @validates("email")
    def normalize_email(self, _field, email):
        return email.strip().lower()


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
    photo_key = db.Column(db.String(255))  # S3 object key, not the image or an expiring URL
    user = db.relationship("User", back_populates="items")
