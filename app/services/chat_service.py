from __future__ import annotations

"""Local conversational feedback controller.

The web runtime uses this small state machine even when the optional Rasa
profile is not running.  Dialogue state stays separate from ABSA inference:
the analyzer supplies aspects/sentiments, while this module only controls the
conversation and safe, deterministic customer-facing wording.
"""

import re
import logging
from dataclasses import dataclass, field

from app.services.nlp_service import get_analyzer
from nlp.schema import ASPECT_VI, SENTIMENT_VI

_STATES: dict[str, "ChatState"] = {}
_RATING = re.compile(r"(?<!\d)([1-5])(?!\d)")
_SERIOUS = ("đổi trả", "hoàn tiền", "bảo hành", "khiếu nại", "liên hệ", "hỗ trợ", "refund", "return")
logger = logging.getLogger(__name__)


@dataclass
class ChatState:
    product_id: int | None = None
    product: dict | None = None
    feedback_text: str = ""
    aspects: list[dict] = field(default_factory=list)
    rating: int | None = None
    phase: str = "idle"
    analysis_available: bool = True
    wants_support: bool = False
    contact_consent: bool | None = None
    contact: str = ""


def reset_chat_states_for_tests() -> None:
    _STATES.clear()


def _result(text: str, *, sender: str, state: ChatState | None = None, ready_to_save: bool = False) -> dict:
    result = {"source": "local_multiturn", "text": text, "ready_to_save": ready_to_save, "sender": sender}
    if state and state.product:
        result["product"] = state.product
    return result


def begin_product_chat(sender: str, product: dict) -> dict:
    """Start/restart a product-bound flow from an authoritative API context."""
    product_id = int(product["product_id"])
    context = {
        "product_id": product_id,
        "product_name": str(product["product_name"]),
        "image_url": str(product["image_url"]),
        "price": product.get("price"),
    }
    state = ChatState(product_id=product_id, product=context, phase="await_rating")
    _STATES[sender] = state
    logger.info("Product chat started product_id=%s phase=%s", product_id, state.phase)
    return _result(
        f"Mình đang ghi nhận trải nghiệm về “{context['product_name']}”. Bạn đánh giá sản phẩm này bao nhiêu sao, từ 1 đến 5?",
        sender=sender,
        state=state,
    )


def _affirm(text: str) -> bool:
    return text.casefold().strip() in {"có", "co", "đúng", "dung", "đúng rồi", "ok", "okay", "ừ", "uh", "yes", "đồng ý"}


def _deny(text: str) -> bool:
    return text.casefold().strip() in {"không", "khong", "không đúng", "ko", "no", "chưa"}


def _rating(text: str) -> int | None:
    match = _RATING.search(text)
    return int(match.group(1)) if match else None


def _needs_support(text: str, aspects: list[dict]) -> bool:
    lower = text.casefold()
    asked_for_help = any(term in lower for term in _SERIOUS)
    service_problem = any(item["aspect"] == "customer_service" and item["sentiment"] == "negative" for item in aspects)
    return asked_for_help or service_problem


def _aspect_sentence(item: dict) -> str:
    aspect = item.get("aspect", "other")
    sentiment = item.get("sentiment", "neutral")
    topic = ASPECT_VI.get(aspect, ASPECT_VI["other"]).casefold()
    if sentiment == "positive":
        sentence = f"Mình ghi nhận bạn hài lòng về {topic}."
    elif sentiment == "negative":
        sentence = f"Mình ghi nhận vấn đề về {topic}."
    elif sentiment == "mixed":
        sentence = f"Mình ghi nhận trải nghiệm về {topic} có cả điểm hài lòng và chưa hài lòng."
    else:
        sentence = f"Mình ghi nhận ý kiến của bạn về {topic}."
    evidence = str(item.get("evidence") or "").strip()
    return f"{sentence} Chi tiết bạn nêu: “{evidence}”." if evidence else sentence


def _issue_specific_response(aspects: list[dict]) -> str:
    # Keep every predicted aspect; do not collapse multi-aspect feedback into
    # a single highest-confidence label.
    sentences = [_aspect_sentence(item) for item in aspects]
    if len(sentences) == 1:
        return sentences[0]
    return " ".join(sentences)


async def chat_reply(message: str, sender: str = "web-user", product_id: int | None = None) -> dict:
    text = message.strip()
    state = _STATES.setdefault(sender, ChatState())
    lower = text.casefold()

    if state.product_id is not None and product_id is not None and state.product_id != product_id:
        return _result("Phiên này đang gắn với sản phẩm khác. Hãy mở lại phần đánh giá của sản phẩm bạn muốn chia sẻ.", sender=sender, state=state)

    if state.phase == "ready_to_save":
        return _result("Đánh giá đã được xác nhận và sẵn sàng lưu.", sender=sender, state=state, ready_to_save=True)
    if state.phase == "await_rating":
        rating = _rating(text)
        if rating is None:
            return _result("Mình cần một mức từ 1 đến 5 sao. Ví dụ: “4 sao”.", sender=sender, state=state)
        state.rating = rating
        state.phase = "await_feedback"
        return _result("Cảm ơn bạn đã chấm %s sao. Bạn có thể chia sẻ điều bạn hài lòng hoặc vấn đề bạn gặp với sản phẩm này không?" % rating, sender=sender, state=state)
    if state.phase == "await_feedback":
        state.feedback_text = text
        return _analyze_into_state(state, sender)
    if state.phase == "await_clarification":
        state.feedback_text = f"{state.feedback_text}\n{text}".strip()
        return _analyze_into_state(state, sender)
    if state.phase == "await_confirmation":
        if _affirm(text):
            return await _after_confirmation(state, sender)
        if _deny(text):
            state.phase = "await_clarification"
            return _result("Cảm ơn bạn đã chỉnh lại. Bạn có thể nói rõ phần nào chưa đúng: sản phẩm, giao hàng, đóng gói, giá hay hỗ trợ của shop?", sender=sender, state=state)
        return _result("Bạn xác nhận giúp mình là phần ghi nhận trên đúng hay chưa đúng nhé.", sender=sender, state=state)
    if state.phase == "await_support":
        if _affirm(text):
            state.wants_support = True
            state.phase = "await_contact_consent"
            return _result("Bạn có đồng ý để shop liên hệ hỗ trợ thêm về vấn đề này không? Bạn có thể trả lời Có hoặc Không.", sender=sender, state=state)
        if _deny(text):
            return _finish(state, sender)
        return _result("Nếu muốn được hỗ trợ thêm, bạn trả lời Có; nếu không, bạn trả lời Không nhé.", sender=sender, state=state)
    if state.phase == "await_contact_consent":
        if _affirm(text):
            state.contact_consent = True
            state.phase = "await_contact"
            return _result("Bạn có thể để lại số điện thoại hoặc email để shop liên hệ. Nếu đổi ý, hãy trả lời “bỏ qua”.", sender=sender, state=state)
        if _deny(text):
            state.contact_consent = False
            return _finish(state, sender)
        return _result("Shop chỉ xin thông tin liên hệ khi bạn đồng ý. Bạn trả lời Có hoặc Không nhé.", sender=sender, state=state)
    if state.phase == "await_contact":
        if lower not in {"bỏ qua", "bo qua", "skip"}:
            state.contact = text
        return _finish(state, sender)

    if any(word in lower for word in ("tạm biệt", "bye", "hẹn gặp")):
        _STATES.pop(sender, None)
        return _result("Cảm ơn bạn đã ghé qua. Hẹn gặp lại!", sender=sender)
    if any(word in lower for word in ("xin chào", "chào", "hello", " hi", "alo")):
        return _result("Chào bạn. Bạn có thể chia sẻ trải nghiệm về sản phẩm, giao hàng, đóng gói, giá hoặc hỗ trợ của shop.", sender=sender)

    # Generic chat remains available outside product detail. Product-bound
    # sessions always begin through begin_product_chat and ask rating first.
    state.feedback_text = text
    return _analyze_into_state(state, sender)


def _analyze_into_state(state: ChatState, sender: str) -> dict:
    try:
        result = get_analyzer().analyze(state.feedback_text)
        state.aspects = list(result.get("aspects") or [])
        state.analysis_available = True
        logger.info(
            "Chat analysis complete product_id=%s phase=%s aspects=%s",
            state.product_id,
            state.phase,
            [item.get("aspect") for item in state.aspects],
        )
    except Exception as exc:
        state.aspects = []
        state.analysis_available = False
        state.phase = "await_confirmation"
        logger.warning("Chat analysis failed product_id=%s error_type=%s", state.product_id, type(exc).__name__)
        return _result("Mình đã ghi nhận nội dung của bạn, nhưng phần phân tích đang tạm thời không phản hồi. Bạn xác nhận giúp mình lưu đúng nội dung này nhé?", sender=sender, state=state)
    if not state.aspects:
        state.phase = "await_clarification"
        return _result("Mình muốn hiểu đúng trải nghiệm của bạn. Vấn đề chính là sản phẩm, giao hàng, đóng gói, giá cả hay hỗ trợ của shop?", sender=sender, state=state)
    state.phase = "await_confirmation"
    return _result(f"{_issue_specific_response(state.aspects)} Mình ghi nhận như vậy có đúng không?", sender=sender, state=state)


async def _after_confirmation(state: ChatState, sender: str) -> dict:
    if state.rating is None:
        state.phase = "await_rating"
        return _result("Cảm ơn bạn đã xác nhận. Bạn muốn chấm sản phẩm bao nhiêu sao, từ 1 đến 5?", sender=sender, state=state)
    if _needs_support(state.feedback_text, state.aspects):
        state.phase = "await_support"
        return _result("Bạn có muốn shop hỗ trợ thêm về vấn đề này không?", sender=sender, state=state)
    return _finish(state, sender)


def _finish(state: ChatState, sender: str) -> dict:
    state.phase = "ready_to_save"
    logger.info("Product chat ready to save product_id=%s", state.product_id)
    return _result("Cảm ơn bạn. Mình đã sẵn sàng lưu đánh giá đã xác nhận của bạn.", sender=sender, state=state, ready_to_save=True)


def consume_confirmed_feedback(sender: str, *, product_id: int | None = None) -> dict | None:
    """Consume one confirmed chat review only for its authoritative product."""
    state = _STATES.get(sender)
    if not state or state.phase != "ready_to_save" or state.rating is None:
        return None
    if state.product_id is not None and state.product_id != product_id:
        return None
    payload = {
        "product_id": state.product_id,
        "text": state.feedback_text,
        "rating": state.rating,
        "contact": state.contact if state.contact_consent else None,
    }
    _STATES.pop(sender, None)
    return payload
