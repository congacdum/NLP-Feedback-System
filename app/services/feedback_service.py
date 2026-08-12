from __future__ import annotations

import json
import logging
import time
from sqlalchemy.orm import Session

from app.models import Feedback, FeedbackAnalysis, Product, User
from app.services.nlp_service import get_analyzer
from app.services.response_builder import build_feedback_response
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
    product = session.get(Product, product_id)
    if product is None:
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
        started = time.perf_counter()
        result = validate_runtime_result(get_analyzer().analyze(feedback.text_raw))
        nlp_ms = round((time.perf_counter() - started) * 1000, 2)
        postprocess_started = time.perf_counter()
        response = build_feedback_response(
            feedback.text_raw,
            result["aspects"],
            product_context={"product_id": product.id, "category": product.category},
        )
        postprocess_ms = round((time.perf_counter() - postprocess_started) * 1000, 2)
        feedback.model_version = str(result.get("model_version") or "unknown")
        feedback.analysis_status = str(result.get("status") or "failed")
        feedback.issue_details_json = json.dumps(response["analysis"], ensure_ascii=False)
        for item in result["aspects"]:
            session.add(FeedbackAnalysis(
                feedback_id=feedback.id,
                aspect=item["aspect"],
                sentiment=item["sentiment"],
                aspect_score=float(item.get("aspect_score", 0.0)),
                sentiment_score=float(item.get("sentiment_score", 0.0)),
            ))
        session.commit()
        session.refresh(feedback)
        # Response data is request-scoped; only structured enrichment is stored.
        feedback.assistant_message = response["assistant_message"]
        feedback.response_analysis = response["analysis"]
        logger.info(
            "feedback_submit feedback_id=%s product_id=%s aspect_count=%s nlp_ms=%s postprocess_ms=%s status=%s",
            feedback.id,
            product_id,
            len(result["aspects"]),
            nlp_ms,
            postprocess_ms,
            feedback.analysis_status,
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
