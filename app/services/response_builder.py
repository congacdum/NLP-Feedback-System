"""Deterministic post-PhoBERT feedback response pipeline.

This module enriches already-authorized ABSA predictions.  It never creates or
changes aspects/sentiments and never invokes an NLP model.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping

from app.config import settings
from nlp.issue_extraction.pipeline import compatible_issue_details, extract_issue_details
from nlp.schema import ASPECT_VI

logger = logging.getLogger(__name__)

FALLBACK_ISSUES = {
    "product_quality": "general_quality",
    "delivery": "general_delivery",
    "customer_service": "general_customer_service",
    "packaging": "general_packaging",
    "price": "general_price",
    "other": "general_feedback",
}

RESPONSE_ASPECT_LABELS = {
    "product_quality": "chất lượng sản phẩm",
    "delivery": "giao hàng",
    "customer_service": "chăm sóc khách hàng",
    "packaging": "đóng gói",
    "price": "giá cả",
    "other": "nội dung bổ sung",
}

# Existing issue-extraction rules retain their canonical IDs.  This map exposes
# stable lower-case application issue IDs without allowing rules to alter ABSA.
ISSUE_IDS = {
    "PRODUCT_DEFECT": "product_defect",
    "PRODUCT_DAMAGED": "product_damaged",
    "WRONG_PRODUCT": "wrong_product",
    "WRONG_VARIANT": "wrong_variant",
    "MISSING_ITEM": "missing_item",
    "POOR_QUALITY": "poor_quality",
    "NOT_AS_DESCRIBED": "not_as_described",
    "USAGE_PROBLEM": "usage_problem",
    "STITCHING_PROBLEM": "poor_quality",
    "SOLE_HARD": "usage_problem",
    "COMFORT_POOR": "usage_problem",
    "SIZE_TOO_SMALL": "wrong_variant",
    "SIZE_TOO_LARGE": "wrong_variant",
    "DELIVERY_DELAY": "late_delivery",
    "DELIVERY_LOST": "lost_delivery",
    "DELIVERY_WRONG": "wrong_delivery",
    "DELIVERY_FAILED": "failed_delivery",
    "DELIVERY_BEHAVIOR": "delivery_behavior",
    "DELIVERY_DAMAGE": "delivery_damage",
    "DELIVERY_FAST": "general_delivery",
    "PACKAGING_DAMAGED": "damaged_package",
    "PACKAGING_POOR": "poor_packaging",
    "PACKAGING_OPENED": "opened_package",
    "PACKAGING_PROTECTION": "insufficient_protection",
    "PACKAGING_POSITIVE": "good_packaging",
    "PRICE_HIGH": "too_expensive",
    "PRICE_CHANGED": "price_changed",
    "VOUCHER_PROBLEM": "voucher_problem",
    "PROMOTION_PROBLEM": "promotion_problem",
    "PRICE_POSITIVE": "good_price",
    "VALUE_FOR_MONEY": "value_for_money",
    "SELLER_SERVICE_NEGATIVE": "general_customer_service",
    "SERVICE_NO_RESPONSE": "no_response",
    "SERVICE_SLOW_RESPONSE": "slow_response",
    "SERVICE_RUDE": "rude_support",
    "SERVICE_POOR_RESOLUTION": "poor_resolution",
    "SELLER_SERVICE_POSITIVE": "helpful_support",
}

ISSUE_PRIORITIES = {
    "product_defect": 100,
    "product_damaged": 100,
    "wrong_product": 95,
    "wrong_variant": 90,
    "missing_item": 90,
    "lost_delivery": 90,
    "damaged_package": 85,
    "delivery_damage": 85,
}

NEGATIVE_ACTIONS = {
    "product_quality": {
        "product_defect": "suggest_return_exchange",
        "product_damaged": "suggest_return_exchange",
        "wrong_product": "suggest_correct_item_resolution",
        "wrong_variant": "suggest_correct_variant_resolution",
        "missing_item": "suggest_missing_item_resolution",
        "poor_quality": "suggest_product_review",
        "not_as_described": "suggest_product_review",
        "usage_problem": "suggest_product_support",
        "general_quality": "acknowledge_quality_problem",
    },
    "delivery": {
        "late_delivery": "suggest_delivery_check",
        "lost_delivery": "suggest_delivery_trace",
        "wrong_delivery": "suggest_delivery_resolution",
        "failed_delivery": "suggest_delivery_check",
        "delivery_behavior": "record_delivery_service_feedback",
        "delivery_damage": "inspect_delivery_damage",
        "general_delivery": "acknowledge_delivery_problem",
    },
    "customer_service": {
        "no_response": "escalate_customer_service",
        "slow_response": "escalate_customer_service",
        "rude_support": "record_customer_service_issue",
        "poor_resolution": "escalate_customer_service",
        "general_customer_service": "acknowledge_customer_service_problem",
    },
    "packaging": {
        "damaged_package": "inspect_package_condition",
        "poor_packaging": "record_packaging_issue",
        "opened_package": "inspect_package_condition",
        "insufficient_protection": "record_packaging_issue",
        "general_packaging": "acknowledge_packaging_problem",
    },
    "price": {
        "too_expensive": "acknowledge_price_feedback",
        "price_changed": "suggest_price_check",
        "voucher_problem": "suggest_promotion_check",
        "promotion_problem": "suggest_promotion_check",
        "general_price": "acknowledge_price_feedback",
    },
    "other": {"general_feedback": "acknowledge_other_problem", "uncategorized_issue": "acknowledge_other_problem"},
}

POSITIVE_ACTIONS = {
    "product_quality": "acknowledge_quality_positive",
    "delivery": "acknowledge_delivery_positive",
    "customer_service": "acknowledge_customer_service_positive",
    "packaging": "acknowledge_packaging_positive",
    "price": "acknowledge_price_positive",
    "other": "acknowledge_other_positive",
}
NEUTRAL_ACTIONS = {
    "product_quality": "acknowledge_quality_neutral",
    "delivery": "acknowledge_delivery_neutral",
    "customer_service": "acknowledge_customer_service_neutral",
    "packaging": "acknowledge_packaging_neutral",
    "price": "acknowledge_price_neutral",
    "other": "acknowledge_general_feedback",
}

ACTION_MESSAGES = {
    "suggest_return_exchange": "Mình rất tiếc vì sản phẩm của bạn đang gặp lỗi. Shop có thể hỗ trợ kiểm tra phương án xử lý hoặc đổi/trả phù hợp theo chính sách.",
    "suggest_correct_item_resolution": "Mình rất tiếc vì sản phẩm nhận được chưa đúng. Shop có thể kiểm tra phương án xử lý phù hợp cho đơn hàng.",
    "suggest_correct_variant_resolution": "Mình rất tiếc vì phiên bản sản phẩm nhận được chưa đúng mong đợi. Shop có thể kiểm tra phương án xử lý phù hợp.",
    "suggest_missing_item_resolution": "Mình rất tiếc vì đơn hàng có thể thiếu sản phẩm hoặc phụ kiện. Shop có thể kiểm tra lại phương án xử lý phù hợp.",
    "suggest_product_review": "Mình rất tiếc vì chất lượng sản phẩm chưa đáp ứng mong đợi. Phản hồi này sẽ được ghi nhận để kiểm tra và cải thiện.",
    "suggest_product_support": "Mình rất tiếc vì trải nghiệm sử dụng sản phẩm chưa thuận lợi. Phản hồi này sẽ được ghi nhận để kiểm tra phương án hỗ trợ phù hợp.",
    "acknowledge_quality_problem": "Mình rất tiếc vì chất lượng sản phẩm chưa đáp ứng mong đợi. Phản hồi này sẽ được ghi nhận để cải thiện.",
    "suggest_delivery_check": "Mình rất tiếc vì thời gian giao hàng chưa đáp ứng mong đợi. Phản hồi này sẽ được ghi nhận để kiểm tra lại quá trình vận chuyển.",
    "suggest_delivery_trace": "Mình rất tiếc vì đơn hàng chưa được nhận như mong đợi. Phản hồi này sẽ được ghi nhận để kiểm tra lại quá trình vận chuyển.",
    "suggest_delivery_resolution": "Mình rất tiếc vì quá trình giao nhận chưa chính xác. Phản hồi này sẽ được ghi nhận để kiểm tra và xử lý phù hợp.",
    "record_delivery_service_feedback": "Mình rất tiếc vì trải nghiệm giao nhận chưa tốt. Phản hồi này sẽ được ghi nhận để cải thiện dịch vụ vận chuyển.",
    "inspect_delivery_damage": "Mình rất tiếc vì quá trình giao nhận có thể đã ảnh hưởng đến đơn hàng. Phản hồi này sẽ được ghi nhận để kiểm tra tình trạng sản phẩm.",
    "acknowledge_delivery_problem": "Mình rất tiếc vì trải nghiệm giao hàng chưa tốt. Phản hồi này sẽ được ghi nhận để kiểm tra lại.",
    "escalate_customer_service": "Mình rất tiếc về trải nghiệm hỗ trợ chưa tốt. Phản hồi này sẽ được ghi nhận để kiểm tra và cải thiện quá trình chăm sóc khách hàng.",
    "record_customer_service_issue": "Mình rất tiếc về trải nghiệm hỗ trợ chưa tốt. Phản hồi này sẽ được ghi nhận để cải thiện chất lượng phục vụ.",
    "acknowledge_customer_service_problem": "Mình rất tiếc về trải nghiệm hỗ trợ chưa tốt. Phản hồi này sẽ được ghi nhận để cải thiện.",
    "inspect_package_condition": "Mình rất tiếc vì tình trạng đóng gói chưa đảm bảo. Shop sẽ ghi nhận để kiểm tra lại bao bì và tình trạng sản phẩm nếu cần.",
    "record_packaging_issue": "Mình rất tiếc vì cách đóng gói chưa đảm bảo. Phản hồi này sẽ được ghi nhận để cải thiện quy trình đóng gói.",
    "acknowledge_packaging_problem": "Mình rất tiếc vì trải nghiệm đóng gói chưa tốt. Phản hồi này sẽ được ghi nhận để cải thiện.",
    "acknowledge_price_feedback": "Mình đã ghi nhận phản hồi về mức giá để shop xem xét và cải thiện.",
    "suggest_price_check": "Mình đã ghi nhận phản hồi về mức giá để shop kiểm tra lại thông tin áp dụng.",
    "suggest_promotion_check": "Mình đã ghi nhận phản hồi về ưu đãi để shop kiểm tra lại chương trình áp dụng.",
    "acknowledge_other_problem": "Mình đã ghi nhận phản hồi của bạn để shop xem xét và cải thiện.",
}

ASPECT_SENTIMENT_MESSAGES = {
    ("product_quality", "positive"): "Cảm ơn bạn đã đánh giá tích cực về chất lượng sản phẩm. Shop rất trân trọng phản hồi của bạn.",
    ("product_quality", "neutral"): "Cảm ơn bạn đã chia sẻ đánh giá về chất lượng sản phẩm. Shop đã ghi nhận phản hồi này để tiếp tục cải thiện.",
    ("product_quality", "mixed"): "Cảm ơn bạn đã chia sẻ. Shop ghi nhận cả những điểm bạn hài lòng và những điểm về chất lượng sản phẩm chưa đáp ứng hoàn toàn mong đợi.",
    ("product_quality", "negative"): "Mình rất tiếc vì chất lượng sản phẩm chưa đáp ứng mong đợi của bạn. Shop đã ghi nhận vấn đề để xem xét hướng hỗ trợ phù hợp.",
    ("delivery", "positive"): "Cảm ơn bạn đã đánh giá tích cực về quá trình giao hàng. Shop rất vui vì đơn hàng đã đến với bạn thuận lợi.",
    ("delivery", "neutral"): "Cảm ơn bạn đã chia sẻ phản hồi về quá trình giao hàng. Nội dung này đã được ghi nhận.",
    ("delivery", "mixed"): "Cảm ơn bạn đã chia sẻ. Shop ghi nhận cả những điểm thuận lợi và phần trải nghiệm giao hàng chưa hoàn toàn đáp ứng mong đợi.",
    ("delivery", "negative"): "Mình rất tiếc vì trải nghiệm giao hàng chưa đáp ứng mong đợi của bạn. Phản hồi này sẽ được ghi nhận để kiểm tra lại quá trình vận chuyển.",
    ("customer_service", "positive"): "Cảm ơn bạn đã đánh giá tích cực về sự hỗ trợ của shop. Phản hồi của bạn là động lực để đội ngũ tiếp tục duy trì chất lượng phục vụ.",
    ("customer_service", "neutral"): "Cảm ơn bạn đã chia sẻ đánh giá về quá trình hỗ trợ. Shop đã ghi nhận phản hồi của bạn.",
    ("customer_service", "mixed"): "Cảm ơn bạn đã chia sẻ. Shop ghi nhận cả những điểm bạn hài lòng và những phần trong quá trình hỗ trợ cần được cải thiện thêm.",
    ("customer_service", "negative"): "Mình rất tiếc vì trải nghiệm hỗ trợ chưa đáp ứng mong đợi của bạn. Phản hồi này sẽ được ghi nhận để kiểm tra và cải thiện quy trình chăm sóc khách hàng.",
    ("packaging", "positive"): "Cảm ơn bạn đã đánh giá tích cực về cách đóng gói sản phẩm. Shop rất vui vì đơn hàng được bảo quản tốt khi đến tay bạn.",
    ("packaging", "neutral"): "Cảm ơn bạn đã chia sẻ đánh giá về cách đóng gói. Phản hồi của bạn đã được ghi nhận.",
    ("packaging", "mixed"): "Cảm ơn bạn đã chia sẻ. Shop ghi nhận cả những điểm tốt và những phần trong cách đóng gói cần được cải thiện thêm.",
    ("packaging", "negative"): "Mình rất tiếc vì tình trạng đóng gói chưa đáp ứng mong đợi. Shop sẽ ghi nhận phản hồi để kiểm tra và cải thiện quy trình đóng gói.",
    ("price", "positive"): "Cảm ơn bạn đã đánh giá tích cực về mức giá sản phẩm. Shop rất vui vì sản phẩm mang lại giá trị phù hợp với mong đợi của bạn.",
    ("price", "neutral"): "Cảm ơn bạn đã chia sẻ đánh giá về mức giá sản phẩm. Phản hồi của bạn đã được ghi nhận.",
    ("price", "mixed"): "Cảm ơn bạn đã chia sẻ. Shop ghi nhận cả những điểm bạn thấy hợp lý và những phần về giá chưa hoàn toàn đáp ứng mong đợi.",
    ("price", "negative"): "Mình đã ghi nhận phản hồi của bạn về mức giá sản phẩm. Nội dung này sẽ được dùng để shop xem xét và cải thiện trải nghiệm mua sắm.",
    ("other", "positive"): "Cảm ơn bạn đã chia sẻ phản hồi tích cực. Ý kiến của bạn đã được ghi nhận.",
    ("other", "neutral"): "Cảm ơn bạn đã chia sẻ. Nội dung phản hồi của bạn đã được ghi nhận.",
    ("other", "mixed"): "Cảm ơn bạn đã chia sẻ những điểm bạn hài lòng cũng như những nội dung còn cần cải thiện. Phản hồi của bạn đã được ghi nhận.",
    ("other", "negative"): "Mình rất tiếc vì trải nghiệm của bạn chưa hoàn toàn như mong đợi. Nội dung bạn phản ánh đã được ghi nhận để xem xét và cải thiện.",
}

ISSUE_MESSAGES = {
    "product_defect": "Mình rất tiếc vì sản phẩm của bạn đang gặp lỗi. Shop có thể hỗ trợ kiểm tra tình trạng sản phẩm và xem xét phương án xử lý hoặc đổi/trả phù hợp theo chính sách.",
    "product_damaged": "Mình rất tiếc vì sản phẩm bị hư hỏng khi bạn nhận hàng. Shop sẽ ghi nhận tình trạng này và có thể hỗ trợ kiểm tra phương án xử lý hoặc đổi/trả phù hợp theo chính sách.",
    "wrong_product": "Mình rất tiếc vì bạn nhận không đúng sản phẩm đã đặt. Shop có thể hỗ trợ kiểm tra đơn hàng và hướng xử lý phù hợp cho trường hợp giao sai sản phẩm.",
    "wrong_variant": "Mình rất tiếc vì sản phẩm nhận được không đúng phân loại bạn đã chọn. Shop có thể kiểm tra lại đơn hàng và hỗ trợ hướng xử lý phù hợp.",
    "missing_item": "Mình rất tiếc vì đơn hàng của bạn đang thiếu sản phẩm hoặc phụ kiện. Shop sẽ ghi nhận để kiểm tra lại nội dung đơn hàng và có hướng hỗ trợ phù hợp.",
    "not_as_described": "Mình rất tiếc vì sản phẩm thực tế chưa phù hợp với thông tin bạn mong đợi từ mô tả. Phản hồi này sẽ được ghi nhận để kiểm tra và có hướng xử lý phù hợp.",
    "late_delivery": "Mình rất tiếc vì thời gian giao hàng lâu hơn mong đợi. Shop sẽ ghi nhận vấn đề này để kiểm tra lại quá trình vận chuyển của đơn hàng.",
    "lost_delivery": "Mình rất tiếc vì bạn chưa nhận được đơn hàng. Shop có thể hỗ trợ kiểm tra lại trạng thái vận chuyển và quá trình giao nhận.",
    "wrong_delivery": "Mình rất tiếc vì quá trình giao nhận chưa chính xác. Shop sẽ ghi nhận để kiểm tra lại thông tin vận chuyển và hướng xử lý phù hợp.",
    "delivery_behavior": "Mình rất tiếc về trải nghiệm trong quá trình giao nhận. Phản hồi của bạn sẽ được ghi nhận để kiểm tra và cải thiện chất lượng dịch vụ vận chuyển.",
    "no_response": "Mình rất tiếc vì bạn chưa nhận được phản hồi khi cần hỗ trợ. Nội dung này sẽ được ghi nhận để kiểm tra lại quá trình chăm sóc khách hàng.",
    "slow_response": "Mình rất tiếc vì thời gian phản hồi hỗ trợ còn chậm. Shop sẽ ghi nhận để cải thiện tốc độ xử lý và hỗ trợ khách hàng.",
    "rude_support": "Mình rất tiếc vì cách hỗ trợ đã khiến bạn chưa hài lòng. Phản hồi này sẽ được ghi nhận để kiểm tra và cải thiện chất lượng phục vụ.",
    "poor_resolution": "Mình rất tiếc vì vấn đề của bạn chưa được hỗ trợ thỏa đáng. Phản hồi này sẽ được ghi nhận để xem xét lại quá trình xử lý.",
    "damaged_package": "Mình rất tiếc vì bao bì của đơn hàng bị hư hỏng. Shop sẽ ghi nhận tình trạng này để kiểm tra lại quá trình đóng gói và vận chuyển.",
    "poor_packaging": "Mình rất tiếc vì cách đóng gói chưa đảm bảo. Phản hồi này sẽ được ghi nhận để cải thiện quy trình bảo vệ sản phẩm.",
    "opened_package": "Mình rất tiếc vì bao bì có dấu hiệu không còn nguyên vẹn. Shop sẽ ghi nhận tình trạng này để kiểm tra và có hướng xử lý phù hợp nếu cần.",
    "insufficient_protection": "Mình rất tiếc vì sản phẩm chưa được bảo vệ tốt trong quá trình đóng gói. Nội dung này sẽ được ghi nhận để cải thiện cách đóng gói sản phẩm.",
    "too_expensive": "Mình đã ghi nhận phản hồi của bạn về mức giá sản phẩm. Shop sẽ xem xét ý kiến này để cải thiện mức độ phù hợp giữa giá và trải nghiệm sản phẩm.",
    "price_changed": "Mình đã ghi nhận vấn đề về sự thay đổi giá. Shop có thể kiểm tra lại mức giá áp dụng tại thời điểm đặt hàng để đối chiếu thông tin.",
    "voucher_problem": "Mình đã ghi nhận vấn đề với voucher. Shop có thể kiểm tra lại điều kiện và chương trình ưu đãi áp dụng tại thời điểm đặt hàng.",
    "promotion_problem": "Mình đã ghi nhận phản hồi về chương trình khuyến mãi. Shop có thể kiểm tra lại điều kiện ưu đãi áp dụng cho đơn hàng.",
}


def _issue_details(text: str, aspects: list[dict], product_context: Mapping | None) -> list[dict]:
    if not settings.issue_extraction_enabled:
        return []
    try:
        candidates = extract_issue_details(text, product_context=product_context)
        return compatible_issue_details(aspects, candidates)
    except Exception:
        logger.exception("Issue extraction failed; preserving canonical ABSA result")
        return []


def _action_for(aspect: str, sentiment: str, issue: str) -> str:
    if sentiment == "positive":
        return POSITIVE_ACTIONS[aspect]
    if sentiment == "neutral":
        return NEUTRAL_ACTIONS[aspect]
    return NEGATIVE_ACTIONS[aspect].get(issue, NEGATIVE_ACTIONS[aspect][FALLBACK_ISSUES[aspect]])


def _priority_for(aspect: str, sentiment: str, issue: str) -> int:
    if issue in ISSUE_PRIORITIES:
        return ISSUE_PRIORITIES[issue]
    if sentiment == "positive":
        return 10
    if sentiment == "neutral":
        return 15
    return {"product_quality": 80, "delivery": 70, "customer_service": 60, "packaging": 60, "price": 50, "other": 30}[aspect]


def _deduplicate_for_response(items: list[dict]) -> list[dict]:
    seen_actions: set[str] = set()
    kept = []
    for item in sorted(items, key=lambda value: (-value["priority"], value["aspect"])):
        if item["action"] in seen_actions:
            continue
        seen_actions.add(item["action"])
        kept.append(item)
    return kept


def _labels(items: list[dict]) -> str:
    values = [RESPONSE_ASPECT_LABELS.get(item["aspect"], ASPECT_VI[item["aspect"]]) for item in items]
    if len(values) < 2:
        return values[0]
    if len(values) == 2:
        return " và ".join(values)
    return ", ".join(values[:-1]) + " và " + values[-1]


def compose_response(items: list[dict]) -> str:
    if not items:
        return "Cảm ơn bạn đã chia sẻ. Phản hồi của bạn đã được ghi nhận."

    ordered = sorted(items, key=lambda value: (-value["priority"], value["aspect"]))
    concerns = [item for item in ordered if item["sentiment"] in {"negative", "mixed"}]
    positives = [item for item in ordered if item["sentiment"] == "positive"]
    neutrals = [item for item in ordered if item["sentiment"] == "neutral"]
    messages: list[str] = []
    if concerns:
        primary = _deduplicate_for_response(concerns)[0]
        if primary["sentiment"] == "mixed":
            messages.append(ASPECT_SENTIMENT_MESSAGES[(primary["aspect"], "mixed")])
        elif primary["issue"] == FALLBACK_ISSUES[primary["aspect"]]:
            messages.append(ASPECT_SENTIMENT_MESSAGES[(primary["aspect"], "negative")])
        else:
            messages.append(
                ISSUE_MESSAGES.get(primary["issue"])
                or ACTION_MESSAGES.get(primary["action"])
                or ASPECT_SENTIMENT_MESSAGES[(primary["aspect"], primary["sentiment"])]
            )
        if len(concerns) > 1:
            secondary = [item for item in concerns if item is not primary]
            messages.append(f"Các phản hồi về {_labels(secondary)} cũng đã được ghi nhận để kiểm tra và cải thiện.")
    if positives:
        if len(positives) == 1 and not concerns and not neutrals:
            messages.append(ASPECT_SENTIMENT_MESSAGES[(positives[0]["aspect"], "positive")])
        else:
            messages.append(f"Cảm ơn bạn cũng đã ghi nhận tích cực về {_labels(positives)}.")
    if neutrals:
        if len(neutrals) == 1 and not concerns and not positives:
            messages.append(ASPECT_SENTIMENT_MESSAGES[(neutrals[0]["aspect"], "neutral")])
        elif not concerns and not positives:
            messages.append(f"Cảm ơn bạn đã chia sẻ đánh giá về {_labels(neutrals)}. Shop đã ghi nhận phản hồi này.")
        else:
            messages.append(f"Thông tin về {_labels(neutrals)} cũng đã được ghi nhận.")
    return " ".join(messages) or "Cảm ơn bạn đã chia sẻ. Phản hồi của bạn đã được ghi nhận."


def build_feedback_response(text: str, aspects: list[dict], *, product_context: Mapping | None = None) -> dict:
    """Build issue/action enrichment without changing canonical predictions."""
    details_by_aspect: dict[str, list[dict]] = {}
    for detail in _issue_details(text, aspects, product_context):
        details_by_aspect.setdefault(str(detail.get("core_aspect") or ""), []).append(detail)

    enriched = []
    for prediction in aspects:
        aspect = prediction["aspect"]
        candidates = details_by_aspect.get(aspect, [])
        mapped = [
            (ISSUE_IDS.get(str(detail.get("canonical_issue") or ""), FALLBACK_ISSUES[aspect]), detail)
            for detail in candidates
        ]
        issue, detail = max(mapped, key=lambda value: _priority_for(aspect, prediction["sentiment"], value[0]), default=(FALLBACK_ISSUES[aspect], None))
        enriched.append({
            **prediction,
            "issue": issue,
            "action": _action_for(aspect, prediction["sentiment"], issue),
            "priority": _priority_for(aspect, prediction["sentiment"], issue),
            "evidence": str(detail.get("evidence") or "") if detail else "",
        })
    return {"analysis": enriched, "assistant_message": compose_response(enriched)}
