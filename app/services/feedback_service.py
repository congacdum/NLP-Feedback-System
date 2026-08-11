from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.models import Feedback, FeedbackAnalysis, Product, User
from app.services.nlp_service import get_analyzer
from nlp.schema import validate_runtime_result

logger = logging.getLogger(__name__)


def create_feedback(session: Session, *, user_id: int, product_id: int, rating: int, text: str) -> Feedback:
    """Persist raw feedback first, then analyze it in a second transaction.

    This deliberately commits the raw row before NLP inference. If inference or
    the process fails later, the customer text is not lost and remains with
    ``analysis_status=pending`` or is marked ``failed`` when the exception is
    recoverable in-process.
    """
    if rating < 1 or rating > 5:
        raise ValueError("Rating phải nằm trong khoảng 1–5")
    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("Feedback không được để trống")
    if session.get(User, user_id) is None:
        raise ValueError("Người dùng không tồn tại")
    if session.get(Product, product_id) is None:
        raise ValueError("Sản phẩm không tồn tại")

    feedback = Feedback(
        user_id=user_id,
        product_id=product_id,
        rating=rating,
        text_raw=clean_text,
        analysis_status="pending",
    )
    session.add(feedback)
    session.commit()  # durability boundary: raw feedback exists before inference
    session.refresh(feedback)
    feedback_id = feedback.id
    logger.info("Raw feedback persisted feedback_id=%s product_id=%s status=pending", feedback_id, product_id)

    try:
        result = validate_runtime_result(get_analyzer().analyze(feedback.text_raw))
        feedback.model_version = str(result.get("model_version") or "unknown")
        feedback.analysis_status = str(result.get("status") or "failed")
        for item in result.get("aspects", []):
            session.add(FeedbackAnalysis(
                feedback_id=feedback.id,
                aspect=item["aspect"],
                sentiment=item["sentiment"],
                aspect_score=float(item.get("aspect_score", 0.0)),
                sentiment_score=float(item.get("sentiment_score", 0.0)),
            ))
        session.commit()
        session.refresh(feedback)
        logger.info(
            "Feedback analysis persisted feedback_id=%s product_id=%s status=%s aspects=%s",
            feedback.id,
            product_id,
            feedback.analysis_status,
            [item["aspect"] for item in result.get("aspects", [])],
        )
        return feedback
    except Exception as exc:
        session.rollback()
        persisted = session.get(Feedback, feedback_id)
        if persisted is not None:
            persisted.analysis_status = "failed"
            persisted.model_version = None
            session.commit()
            session.refresh(persisted)
            logger.warning("Feedback analysis failed feedback_id=%s product_id=%s error_type=%s", feedback_id, product_id, type(exc).__name__)
            return persisted
        raise
