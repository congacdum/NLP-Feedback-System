from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from sqlalchemy import delete, func, select
    from app.bootstrap import initialize_database
    from app.db import session_scope
    from app.models import Feedback, FeedbackAnalysis, Product
    HAS_SQLALCHEMY = True
except ModuleNotFoundError:
    # Keep catalog materialisation usable on a data-preparation machine that
    # has only the standard library. The web app itself still uses SQLAlchemy.
    HAS_SQLALCHEMY = False


def import_sqlite(rows: list[dict], *, replace: bool) -> dict:
    db_path = ROOT / "data" / "app.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY, external_id VARCHAR(100) UNIQUE,
            name VARCHAR(255) NOT NULL, category VARCHAR(120) NOT NULL,
            price FLOAT NOT NULL DEFAULT 0, description TEXT NOT NULL DEFAULT '',
            image_path TEXT, image_url TEXT, created_at DATETIME NOT NULL)""")
        if replace:
            try:
                feedback_count = connection.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            except sqlite3.OperationalError:
                feedback_count = 0
            if feedback_count:
                raise SystemExit("Refusing --replace: existing feedback references the current catalog. Export/migrate deliberately instead.")
            connection.execute("DELETE FROM products")
        created = updated = 0
        now = datetime.now(timezone.utc).isoformat()
        for row in rows:
            external_id = str(row.get("external_id") or row.get("id"))
            values = (str(row["name"]), str(row.get("category") or "Khác"), float(row["price"]) if row.get("price") not in (None, "") else 0.0, str(row.get("description") or row["name"]), row.get("image_path"), row.get("image_url"), now, external_id)
            exists = connection.execute("SELECT id FROM products WHERE external_id=?", (external_id,)).fetchone()
            if exists:
                connection.execute("UPDATE products SET name=?, category=?, price=?, description=?, image_path=?, image_url=?, created_at=? WHERE external_id=?", values)
                updated += 1
            else:
                connection.execute("INSERT INTO products (name,category,price,description,image_path,image_url,created_at,external_id) VALUES (?,?,?,?,?,?,?,?)", values)
                created += 1
        connection.commit()
        return {"imported": len(rows), "created": created, "updated": updated, "replace": replace, "mode": "sqlite-stdlib"}
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a materialized Lazada metadata catalog into the application database")
    parser.add_argument("json_file", type=Path)
    parser.add_argument("--replace", action="store_true", help="Replace catalog only when there is no feedback referencing existing products")
    parser.add_argument("--reset-catalog-and-feedback", action="store_true", help="Explicitly delete current product feedback/analysis rows and replace the catalog")
    args = parser.parse_args()
    rows = json.loads(args.json_file.read_text(encoding="utf-8"))
    if args.replace and args.reset_catalog_and_feedback:
        raise SystemExit("Use either --replace or --reset-catalog-and-feedback, not both")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("Catalog JSON must be a non-empty array")
    external_ids = [str(row.get("external_id") or row.get("id") or "") for row in rows]
    if not all(external_ids) or len(set(external_ids)) != len(external_ids):
        raise SystemExit("Catalog has missing or duplicate external_id values")

    if not HAS_SQLALCHEMY:
        if args.reset_catalog_and_feedback:
            db_path = ROOT / "data" / "app.db"
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("PRAGMA foreign_keys=OFF")
                for table in ("feedback_analysis", "feedback", "products"):
                    try: connection.execute(f"DELETE FROM {table}")
                    except sqlite3.OperationalError: pass
                connection.commit()
            finally:
                connection.close()
            print("Reset product, feedback, and analysis data explicitly requested.")
        print(json.dumps(import_sqlite(rows, replace=args.replace or args.reset_catalog_and_feedback), ensure_ascii=False))
        return
    initialize_database()
    with session_scope() as session:
        if args.reset_catalog_and_feedback:
            session.execute(delete(FeedbackAnalysis))
            session.execute(delete(Feedback))
            session.execute(delete(Product))
        elif args.replace:
            feedback_count = int(session.scalar(select(func.count(Feedback.id))) or 0)
            if feedback_count:
                raise SystemExit("Refusing --replace: existing feedback references the current catalog. Export/migrate deliberately instead.")
            session.execute(delete(Product))
        existing = {product.external_id: product for product in session.scalars(select(Product).where(Product.external_id.in_(external_ids))).all()}
        created = updated = 0
        for row in rows:
            external_id = str(row.get("external_id") or row.get("id"))
            product = existing.get(external_id)
            values = {
                "name": str(row["name"]),
                "category": str(row.get("category") or "Khác"),
                "price": float(row["price"]) if row.get("price") not in (None, "") else 0.0,
                "description": str(row.get("description") or row["name"]),
                "image_path": row.get("image_path"),
                "image_url": row.get("image_url"),
            }
            if product is None:
                session.add(Product(external_id=external_id, **values))
                created += 1
            else:
                for key, value in values.items():
                    setattr(product, key, value)
                updated += 1
    print(json.dumps({"imported": len(rows), "created": created, "updated": updated, "replace": args.replace or args.reset_catalog_and_feedback, "reset_feedback": args.reset_catalog_and_feedback}, ensure_ascii=False))


if __name__ == "__main__":
    main()
