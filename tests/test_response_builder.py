from __future__ import annotations

import pytest

from app.services import response_builder


def prediction(aspect: str, sentiment: str) -> dict:
    return {"aspect": aspect, "sentiment": sentiment, "aspect_score": 0.9, "sentiment_score": 0.9}


def test_multi_aspect_response_uses_issue_priority_without_changing_predictions():
    result = response_builder.build_feedback_response(
        "Máy không lên nguồn, hộp bị móp và giao hàng quá chậm.",
        [
            prediction("product_quality", "negative"),
            prediction("delivery", "negative"),
            prediction("packaging", "negative"),
        ],
        product_context={"product_id": 1, "category": "electronics"},
    )

    by_aspect = {item["aspect"]: item for item in result["analysis"]}
    assert by_aspect["product_quality"]["issue"] == "product_defect"
    assert by_aspect["product_quality"]["action"] == "suggest_return_exchange"
    assert by_aspect["packaging"]["issue"] == "damaged_package"
    assert by_aspect["delivery"]["issue"] == "late_delivery"
    assert by_aspect["product_quality"]["priority"] > by_aspect["packaging"]["priority"] > by_aspect["delivery"]["priority"]
    assert result["assistant_message"].count("Mình rất tiếc") == 1
    assert "đóng gói" in result["assistant_message"].casefold()
    assert "giao hàng" in result["assistant_message"].casefold()


def test_positive_aspects_do_not_create_escalation_response():
    result = response_builder.build_feedback_response(
        "Sản phẩm đẹp, giao nhanh, đóng gói kỹ và giá hợp lý.",
        [
            prediction("product_quality", "positive"),
            prediction("delivery", "positive"),
            prediction("packaging", "positive"),
            prediction("price", "positive"),
        ],
        product_context={"product_id": 1, "category": "fashion"},
    )

    assert all(item["action"].startswith("acknowledge_") for item in result["analysis"])
    assert "đổi/trả" not in result["assistant_message"].casefold()
    assert "cảm ơn" in result["assistant_message"].casefold()


@pytest.mark.parametrize(
    ("aspect", "sentiment", "expected_phrase"),
    [
        ("product_quality", "positive", "chất lượng sản phẩm"),
        ("product_quality", "neutral", "chất lượng sản phẩm"),
        ("product_quality", "mixed", "chất lượng sản phẩm"),
        ("product_quality", "negative", "chất lượng sản phẩm"),
        ("delivery", "positive", "giao hàng"),
        ("delivery", "neutral", "giao hàng"),
        ("delivery", "mixed", "giao hàng"),
        ("delivery", "negative", "giao hàng"),
        ("customer_service", "positive", "hỗ trợ"),
        ("customer_service", "neutral", "hỗ trợ"),
        ("customer_service", "mixed", "hỗ trợ"),
        ("customer_service", "negative", "hỗ trợ"),
        ("packaging", "positive", "đóng gói"),
        ("packaging", "neutral", "đóng gói"),
        ("packaging", "mixed", "đóng gói"),
        ("packaging", "negative", "đóng gói"),
        ("price", "positive", "mức giá"),
        ("price", "neutral", "mức giá"),
        ("price", "mixed", "giá"),
        ("price", "negative", "mức giá"),
        ("other", "positive", "phản hồi tích cực"),
        ("other", "neutral", "phản hồi"),
        ("other", "mixed", "cải thiện"),
        ("other", "negative", "trải nghiệm"),
    ],
)
def test_single_aspect_sentiment_has_a_specific_customer_response(aspect, sentiment, expected_phrase):
    result = response_builder.build_feedback_response(
        "Nội dung kiểm thử.",
        [prediction(aspect, sentiment)],
        product_context={"product_id": 1, "category": "fashion"},
    )

    assert expected_phrase in result["assistant_message"].casefold()
    if sentiment == "positive":
        assert "đổi/trả" not in result["assistant_message"].casefold()


def test_specific_issue_response_is_preferred_for_negative_feedback():
    result = response_builder.build_feedback_response(
        "Máy không lên nguồn.",
        [prediction("product_quality", "negative")],
        product_context={"product_id": 1, "category": "electronics"},
    )

    assert result["analysis"][0]["issue"] == "product_defect"
    assert "đổi/trả" in result["assistant_message"].casefold()


def test_six_aspect_response_groups_concerns_without_repeating_apology():
    aspects = [
        prediction("product_quality", "negative"),
        prediction("delivery", "negative"),
        prediction("customer_service", "negative"),
        prediction("packaging", "negative"),
        prediction("price", "negative"),
        prediction("other", "negative"),
    ]
    message = response_builder.build_feedback_response(
        "Nội dung kiểm thử.", aspects, product_context={"product_id": 1, "category": "fashion"}
    )["assistant_message"]

    assert message.count("Mình rất tiếc") <= 1
    for phrase in ("giao hàng", "chăm sóc khách hàng", "đóng gói", "giá cả", "nội dung bổ sung"):
        assert phrase in message.casefold()


def test_negated_issue_keyword_does_not_override_phobert_prediction():
    result = response_builder.build_feedback_response(
        "Giao hàng không chậm.",
        [prediction("delivery", "negative")],
        product_context={"product_id": 1, "category": "fashion"},
    )

    item = result["analysis"][0]
    assert item["sentiment"] == "negative"
    assert item["issue"] == "general_delivery"


def test_issue_extractor_failure_uses_fallback_without_affecting_analysis(monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("forced issue failure")

    monkeypatch.setattr(response_builder, "extract_issue_details", fail)
    result = response_builder.build_feedback_response(
        "Giá hơi cao.",
        [prediction("price", "negative")],
        product_context={"product_id": 1, "category": "fashion"},
    )

    assert result["analysis"][0]["issue"] == "general_price"
    assert result["analysis"][0]["sentiment"] == "negative"


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 6])
def test_response_composer_handles_one_to_six_aspects(count):
    all_aspects = [
        "product_quality", "delivery", "customer_service", "packaging", "price", "other",
    ]
    sentiments = ["negative", "positive", "neutral", "mixed", "negative", "positive"]
    result = response_builder.build_feedback_response(
        "Phản hồi kiểm thử có nhiều nội dung.",
        [prediction(aspect, sentiment) for aspect, sentiment in zip(all_aspects[:count], sentiments[:count])],
        product_context={"product_id": 1, "category": "fashion"},
    )

    assert len(result["analysis"]) == count
    assert result["assistant_message"]
