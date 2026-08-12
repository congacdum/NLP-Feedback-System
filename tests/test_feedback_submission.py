from __future__ import annotations

import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models
from app.services.analytics_service import issue_summary
from app.services import feedback_service


class CountingAnalyzer:
    def __init__(self):
        self.calls = 0

    def analyze(self, _text: str) -> dict:
        self.calls += 1
        return {
            "status": "ok",
            "model_version": "test-transformer",
            "aspects": [
                {"aspect": "product_quality", "sentiment": "negative", "aspect_score": 0.95, "sentiment_score": 0.93},
                {"aspect": "delivery", "sentiment": "negative", "aspect_score": 0.92, "sentiment_score": 0.91},
                {"aspect": "packaging", "sentiment": "negative", "aspect_score": 0.89, "sentiment_score": 0.88},
            ],
        }


def test_submit_runs_analyzer_once_and_persists_every_aspect(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    models.Base.metadata.create_all(engine)
    analyzer = CountingAnalyzer()
    monkeypatch.setattr(feedback_service, "get_analyzer", lambda: analyzer)

    with Session(engine, expire_on_commit=False) as session:
        user = models.User(name="Customer", email="customer@test.local", password_hash="x", role="customer")
        product = models.Product(name="Demo product", category="electronics", price=1.0, description="")
        session.add_all([user, product])
        session.commit()

        feedback = feedback_service.create_feedback(
            session,
            user_id=user.id,
            product_id=product.id,
            rating=2,
            text="Máy không lên nguồn, hộp bị móp và giao hàng quá chậm.",
        )

        assert analyzer.calls == 1
        assert feedback.analysis_status == "ok"
        rows = session.scalars(
            select(models.FeedbackAnalysis).where(models.FeedbackAnalysis.feedback_id == feedback.id)
        ).all()
        assert {(row.aspect, row.sentiment) for row in rows} == {
            ("product_quality", "negative"),
            ("delivery", "negative"),
            ("packaging", "negative"),
        }
        details = json.loads(feedback.issue_details_json)
        assert {item["issue"] for item in details} == {"product_defect", "late_delivery", "damaged_package"}
        assert feedback.assistant_message
        summary = issue_summary(session)
        assert {item["issue"] for item in summary} == {"product_defect", "late_delivery", "damaged_package"}
