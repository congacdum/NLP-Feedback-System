from __future__ import annotations

"""Exercise the real product-chat path against a configured local Transformer.

This script is intentionally independent from pytest's demo-backend fixture.
It uses the application's normal lifespan, API routes, persistence service and
seller analytics endpoint.  It never imports a dataset or evaluator.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import Feedback, FeedbackAnalysis, Product


def main() -> None:
    output = ROOT / "model_artifacts" / "experimental_phobert_absa_v1" / "runtime_checks" / "transformer_chat_e2e.json"
    with TestClient(app) as client:
        health = client.get("/health").json()
        if health.get("nlp_backend") != "transformer" or health.get("scientific_runtime") is not True:
            raise RuntimeError(f"E2E requires real strict Transformer runtime, got {health}")
        with session_scope() as session:
            product = session.scalar(select(Product).order_by(Product.id))
            if product is None:
                raise RuntimeError("E2E database has no product; enable an isolated demo catalog for this check")
            product_id = product.id

        detail = client.get(f"/products/{product_id}")
        if detail.status_code != 200 or f'data-chat-product-id="{product_id}"' not in detail.text:
            raise RuntimeError("Product detail did not expose authoritative chat product context")
        login = client.post("/auth/login", data={"email": "customer@example.com", "password": "customer123", "next": f"/products/{product_id}"}, follow_redirects=False)
        if login.status_code != 303:
            raise RuntimeError("Customer login failed in isolated E2E database")
        sender = "transformer-runtime-e2e"
        started = client.post("/api/chat/start", json={"sender": sender, "product_id": product_id})
        if started.status_code != 200 or started.json().get("product", {}).get("product_id") != product_id:
            raise RuntimeError("Chat did not bind to the authoritative product ID")
        client.post("/api/chat", json={"sender": sender, "product_id": product_id, "message": "4 sao"}).raise_for_status()
        analyzed = client.post("/api/chat", json={"sender": sender, "product_id": product_id, "message": "Ship lâu, hộp móp và nhân viên hỗ trợ còn trả lời khó chịu."})
        analyzed.raise_for_status()
        reply = analyzed.json()
        confirmed = client.post("/api/chat", json={"sender": sender, "product_id": product_id, "message": "đúng"})
        confirmed.raise_for_status()
        save_reply = confirmed.json()
        # A real customer-service negative prediction may correctly offer
        # support before saving. Decline it here to prove contact remains
        # optional; no contact data is ever submitted by this test.
        if not save_reply.get("feedback_id") and "hỗ trợ" in save_reply.get("text", "").casefold():
            save_reply = client.post("/api/chat", json={"sender": sender, "product_id": product_id, "message": "không"}).json()
        feedback_id = save_reply.get("feedback_id")
        if not feedback_id:
            raise RuntimeError(f"Confirmed Transformer chat did not save feedback: {save_reply}")
        with session_scope() as session:
            feedback = session.get(Feedback, feedback_id)
            rows = session.scalars(select(FeedbackAnalysis).where(FeedbackAnalysis.feedback_id == feedback_id)).all()
            if feedback is None or feedback.product_id != product_id or feedback.rating != 4:
                raise RuntimeError("Persisted feedback product/rating did not match chat context")
            if not rows:
                raise RuntimeError("Transformer analysis did not persist any aspect row")
            persisted = {
                "feedback_id": feedback_id,
                "product_id": feedback.product_id,
                "rating": feedback.rating,
                "analysis_status": feedback.analysis_status,
                "model_version": feedback.model_version,
                "aspects": [{"aspect": row.aspect, "sentiment": row.sentiment} for row in rows],
            }

        client.post("/auth/logout")
        seller_login = client.post("/seller/auth/login", data={"email": "seller@example.com", "password": "seller123"}, follow_redirects=False)
        if seller_login.status_code != 303:
            raise RuntimeError("Seller login failed in isolated E2E database")
        analytics = client.get("/api/analytics/summary")
        analytics.raise_for_status()
        matrix = {item["aspect"]: item["total"] for item in analytics.json()["aspects"]}
        for row in persisted["aspects"]:
            if matrix.get(row["aspect"], 0) < 1:
                raise RuntimeError(f"Seller analytics did not aggregate persisted aspect {row['aspect']}")

    report = {
        "backend": health["nlp_backend"],
        "scientific_runtime": health["scientific_runtime"],
        "product_context": started.json()["product"],
        "chat_analysis_reply": reply["text"],
        "persistence": persisted,
        "seller_aspect_totals": matrix,
        "contact_requested": "liên hệ" in reply["text"].casefold(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "persistence": persisted, "seller_aspect_totals": matrix}, ensure_ascii=False))


if __name__ == "__main__":
    main()
