"""Home-page listing. The /posts JSON API keeps its own query."""

from sqlalchemy import or_

from app.extensions import db
from app.models import Item


def _escape_like(term):
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def browse_context(args):
    q = (args.get("q") or "").strip()
    category = (args.get("category") or "").strip()
    listing_type = (args.get("listing_type") or "").strip().lower()
    if listing_type not in ("lost", "found"):
        listing_type = ""
    sort = (args.get("sort") or "newest").strip().lower()
    if sort not in ("newest", "oldest"):
        sort = "newest"

    statement = db.select(Item)
    if q:
        pattern = f"%{_escape_like(q)}%"
        statement = statement.where(or_(
            Item.title.ilike(pattern, escape="\\"),
            Item.description.ilike(pattern, escape="\\"),
        ))
    if category:
        statement = statement.where(Item.category == category)
    if listing_type:
        statement = statement.where(Item.listing_type == listing_type)

    date_order = Item.date_reported.desc() if sort == "newest" else Item.date_reported.asc()
    statement = statement.order_by(date_order, Item.created_at.desc())
    items = db.session.execute(statement).scalars().all()
    return {
        "items": items,
        "q": q,
        "category": category,
        "listing_type": listing_type,
        "sort": sort,
        "filtering": bool(q or category or listing_type),
    }
