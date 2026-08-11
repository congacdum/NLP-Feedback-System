from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence

ASPECTS: tuple[str, ...] = (
    "product_quality",
    "delivery",
    "customer_service",
    "packaging",
    "price",
    "other",
)
SENTIMENTS: tuple[str, ...] = ("positive", "neutral", "negative", "mixed")

ASPECT_VI: Dict[str, str] = {
    "product_quality": "Chất lượng sản phẩm",
    "delivery": "Giao hàng",
    "customer_service": "Dịch vụ CSKH",
    "packaging": "Đóng gói",
    "price": "Giá cả",
    "other": "Khác",
}
SENTIMENT_VI: Dict[str, str] = {
    "positive": "Tích cực",
    "neutral": "Trung tính",
    "negative": "Tiêu cực",
    "mixed": "Hỗn hợp",
}


@dataclass(frozen=True)
class Annotation:
    aspect: str
    sentiment: str

    def __post_init__(self) -> None:
        if self.aspect not in ASPECTS:
            raise ValueError(f"Unknown aspect: {self.aspect}")
        if self.sentiment not in SENTIMENTS:
            raise ValueError(f"Unknown sentiment: {self.sentiment}")


def normalize_annotations(items: Iterable[Mapping[str, str]]) -> List[Annotation]:
    """Validate and merge duplicate aspect annotations conservatively.

    If the same aspect contains both positive and negative annotations, it becomes
    ``mixed``. Neutral does not erase an explicit positive/negative polarity.
    """
    grouped: Dict[str, set[str]] = {}
    for item in items:
        ann = Annotation(aspect=str(item["aspect"]), sentiment=str(item["sentiment"]))
        grouped.setdefault(ann.aspect, set()).add(ann.sentiment)

    out: List[Annotation] = []
    for aspect in ASPECTS:
        values = grouped.get(aspect)
        if not values:
            continue
        if "mixed" in values or ({"positive", "negative"} <= values):
            sentiment = "mixed"
        elif "negative" in values:
            sentiment = "negative"
        elif "positive" in values:
            sentiment = "positive"
        else:
            sentiment = "neutral"
        out.append(Annotation(aspect=aspect, sentiment=sentiment))
    return out


def pair_labels(annotations: Sequence[Mapping[str, str]] | Sequence[Annotation]) -> set[str]:
    labels: set[str] = set()
    for item in annotations:
        if isinstance(item, Annotation):
            labels.add(f"{item.aspect}#{item.sentiment}")
        else:
            labels.add(f"{item['aspect']}#{item['sentiment']}")
    return labels


def validate_runtime_result(result: Mapping) -> dict:
    """Validate analyzer output before it can be persisted.

    Returns a shallow normalized copy. Invalid labels, duplicate aspects, unknown
    status values, or out-of-range scores raise ``ValueError`` so the feedback
    row is marked failed instead of silently corrupting analytics.
    """
    status = str(result.get("status") or "")
    if status not in {"ok", "no_aspect"}:
        raise ValueError(f"Invalid analyzer status: {status!r}")
    raw_aspects = result.get("aspects") or []
    if not isinstance(raw_aspects, list):
        raise ValueError("Analyzer aspects must be a list")
    seen: set[str] = set()
    aspects: list[dict] = []
    for item in raw_aspects:
        if not isinstance(item, Mapping):
            raise ValueError("Each analyzer aspect must be an object")
        aspect = str(item.get("aspect") or "")
        sentiment = str(item.get("sentiment") or "")
        Annotation(aspect=aspect, sentiment=sentiment)
        if aspect in seen:
            raise ValueError(f"Duplicate analyzer aspect: {aspect}")
        seen.add(aspect)
        aspect_score = float(item.get("aspect_score", 0.0))
        sentiment_score = float(item.get("sentiment_score", 0.0))
        if not 0.0 <= aspect_score <= 1.0 or not 0.0 <= sentiment_score <= 1.0:
            raise ValueError("Analyzer scores must be within [0, 1]")
        aspects.append({
            "aspect": aspect,
            "sentiment": sentiment,
            "aspect_score": aspect_score,
            "sentiment_score": sentiment_score,
        })
    if status == "ok" and not aspects:
        raise ValueError("status=ok requires at least one aspect")
    if status == "no_aspect" and aspects:
        raise ValueError("status=no_aspect cannot contain aspects")
    normalized = dict(result)
    normalized["status"] = status
    normalized["aspects"] = aspects
    return normalized
