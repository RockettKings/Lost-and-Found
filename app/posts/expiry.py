"""Automatically close (mark resolved) posts that have been open too long."""

import time
from datetime import timedelta

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Item, utc_now

CHECK_INTERVAL_SECONDS = 60 * 60


def close_expired_posts(days=None, now=None):
    """Mark open posts created more than `days` ago as resolved; return how many.

    Uses created_at (set by the server) rather than date_reported, which the poster
    chooses and could backdate.
    """
    days = current_app.config["POST_AUTO_CLOSE_DAYS"] if days is None else days
    cutoff = (now or utc_now()) - timedelta(days=days)
    result = db.session.execute(
        db.update(Item)
        .where(Item.resolved.is_(False), Item.created_at < cutoff)
        .values(resolved=True)
    )
    db.session.commit()
    return result.rowcount


def maybe_close_expired_posts(app):
    """Run close_expired_posts at most once per CHECK_INTERVAL_SECONDS per process."""
    state = app.extensions.setdefault("post_expiry", {"last_run": None})
    now = time.monotonic()
    if state["last_run"] is not None and now - state["last_run"] < CHECK_INTERVAL_SECONDS:
        return
    state["last_run"] = now
    try:
        closed = close_expired_posts()
    except SQLAlchemyError:
        # Never fail the visitor's request because of housekeeping.
        db.session.rollback()
        app.logger.exception("Could not auto-close expired posts.")
        return
    if closed:
        app.logger.info("Auto-closed %s post(s) older than %s days.",
                        closed, app.config["POST_AUTO_CLOSE_DAYS"])
