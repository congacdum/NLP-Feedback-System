from __future__ import annotations

import math

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Feedback, Product


def _bounded_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    """Parse query input without letting a malformed page blank the catalog."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return min(maximum, max(minimum, number))


def parse_optional_float(value: object) -> float | None:
    """Convert optional HTML query values without rejecting blank input."""
    if value is None:
        return None
    try:
        text = str(value).strip()
        number = float(text) if text else None
    except (TypeError, ValueError):
        return None
    return number if number is not None and math.isfinite(number) else None


def pagination_window(page: int, pages: int, radius: int = 2) -> list[int | None]:
    """Return page numbers with None as a compact ellipsis marker."""
    candidates = {1, pages, *range(max(1, page - radius), min(pages, page + radius) + 1)}
    window: list[int | None] = []
    previous = 0
    for number in sorted(candidates):
        if number - previous > 1:
            window.append(None)
        window.append(number)
        previous = number
    return window


def _catalog_scope(session: Session):
    """Hide legacy demo fixtures once a real catalog has been imported.

    Existing demo rows remain addressable so historic demo feedback is not
    destroyed, but the customer catalog never silently falls back to them.
    """
    real_exists = session.scalar(select(Product.id).where(~Product.external_id.like("demo-%")).limit(1)) is not None
    return Product.external_id.not_like("demo-%") if real_exists and not settings.dev_demo_catalog else None


def resolved_image_url(product: Product) -> str:
    if product.image_url:
        return product.image_url
    if product.image_path:
        return settings.product_hf_base.rstrip("/") + "/" + product.image_path.lstrip("/")
    return "/static/img/product-placeholder.svg"


def category_counts(session: Session) -> list[dict]:
    stmt = (
        select(Product.category, func.count(Product.id))
        .group_by(Product.category)
        .order_by(Product.category)
    )
    scope = _catalog_scope(session)
    if scope is not None:
        stmt = stmt.where(scope)
    rows = session.execute(stmt).all()
    return [{"name": str(category), "count": int(count)} for category, count in rows]


def list_products(
    session: Session,
    *,
    q: str = "",
    category: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    min_rating: float | None = None,
    sort: str = "newest",
    page: int = 1,
    limit: int = 20,
):
    rating_sub = (
        select(
            Feedback.product_id.label("pid"),
            func.avg(Feedback.rating).label("avg_rating"),
            func.count(Feedback.id).label("review_count"),
        )
        .group_by(Feedback.product_id)
        .subquery()
    )
    stmt = (
        select(Product, rating_sub.c.avg_rating, rating_sub.c.review_count)
        .outerjoin(rating_sub, Product.id == rating_sub.c.pid)
    )
    scope = _catalog_scope(session)
    if scope is not None:
        stmt = stmt.where(scope)
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(or_(Product.name.ilike(needle), Product.description.ilike(needle)))
    if category:
        stmt = stmt.where(Product.category == category)
    if min_price is not None or max_price is not None:
        # Upstream Lazada metadata does not document price; price=0 means unknown
        # rather than free. Price filters therefore operate on known-price rows.
        stmt = stmt.where(Product.price > 0)
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if min_rating is not None:
        # Products without reviews have rating 0; a positive rating filter excludes them.
        stmt = stmt.where(func.coalesce(rating_sub.c.avg_rating, 0.0) >= min_rating)

    # Count the same filtered relational query before pagination/order to avoid
    # drifting count logic when a filter is added later.
    total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)

    if sort == "price_asc":
        stmt = stmt.order_by(case((Product.price <= 0, 1), else_=0).asc(), Product.price.asc(), Product.id.desc())
    elif sort == "price_desc":
        stmt = stmt.order_by(Product.price.desc(), Product.id.desc())
    elif sort == "rating":
        stmt = stmt.order_by(func.coalesce(rating_sub.c.avg_rating, 0).desc(), Product.id.desc())
    else:
        stmt = stmt.order_by(Product.id.desc())

    page = _bounded_int(page, default=1, minimum=1, maximum=1_000_000)
    limit = _bounded_int(limit, default=20, minimum=1, maximum=50)
    pages = max(1, (total + limit - 1) // limit)
    # An out-of-range query parameter previously produced an empty grid. Clamp
    # it before OFFSET so every valid catalog URL renders a real page.
    page = min(page, pages)
    rows = session.execute(stmt.offset((page - 1) * limit).limit(limit)).all()
    items = []
    for product, avg_rating, review_count in rows:
        items.append({
            "product": product,
            "avg_rating": float(avg_rating or 0.0),
            "review_count": int(review_count or 0),
            "image_url_resolved": resolved_image_url(product),
        })
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
        "page_window": pagination_window(page, pages),
    }


def product_rating(session: Session, product_id: int) -> tuple[float, int]:
    avg, count = session.execute(
        select(func.avg(Feedback.rating), func.count(Feedback.id)).where(Feedback.product_id == product_id)
    ).one()
    return float(avg or 0.0), int(count or 0)
