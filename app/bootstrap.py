from __future__ import annotations

import json
from pathlib import Path
from sqlalchemy import select

from app.config import ROOT, settings
from app.db import Base, engine, session_scope
from app.models import Product, User
from app.security import hash_password


def initialize_database() -> None:
    Base.metadata.create_all(engine)
    with session_scope() as session:
        if session.scalar(select(User.id).limit(1)) is None:
            session.add_all([
                User(name="Demo Customer", email="customer@example.com", password_hash=hash_password("customer123"), role="customer"),
                User(name="Demo Seller", email="seller@example.com", password_hash=hash_password("seller123"), role="seller"),
            ])
        if settings.dev_demo_catalog and session.scalar(select(Product.id).limit(1)) is None:
            demo = json.loads((ROOT/"data/demo_products.json").read_text(encoding="utf-8"))
            for row in demo:
                session.add(Product(
                    external_id=row.get("external_id"), name=row["name"], category=row["category"],
                    price=float(row.get("price",0)), description=row.get("description", ""),
                    image_path=row.get("image_path"), image_url=row.get("image_url"),
                ))
