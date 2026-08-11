"""Central canonical-issue map adapted from ``nlp_engine.zip`` donor rules.

The map deliberately terminates at one of the project's six existing aspects;
canonical issues are explanatory sub-details, never new ABSA labels.
"""
from __future__ import annotations

from dataclasses import dataclass


CANONICAL_ISSUE_TO_ASPECT: dict[str, str] = {
    "STITCHING_PROBLEM": "product_quality",
    "SOLE_HARD": "product_quality",
    "COMFORT_POOR": "product_quality",
    "SIZE_TOO_SMALL": "product_quality",
    "SIZE_TOO_LARGE": "product_quality",
    "DELIVERY_DELAY": "delivery",
    "DELIVERY_FAST": "delivery",
    "PACKAGING_DAMAGED": "packaging",
    "PACKAGING_POSITIVE": "packaging",
    "PRICE_HIGH": "price",
    "PRICE_POSITIVE": "price",
    "SELLER_SERVICE_NEGATIVE": "customer_service",
    "SELLER_SERVICE_POSITIVE": "customer_service",
}


@dataclass(frozen=True)
class IssueRule:
    canonical_issue: str
    pattern: str
    # Empty means the issue is category-independent.  Non-empty terms are
    # checked only against the authoritative Product.category supplied by the
    # main application, never against a guessed product name.
    allowed_category_terms: tuple[str, ...] = ()
    # Some complaint predicates themselves contain a negator, for example
    # “CSKH không trả lời”.  They are not a negated issue assertion.
    allow_negated_match: bool = False

    @property
    def core_aspect(self) -> str:
        return CANONICAL_ISSUE_TO_ASPECT[self.canonical_issue]


# Patterns are intentionally conjunctive and local to a clause.  Broad donor
# terms such as ``hỏng``, ``tốt`` or ``đẹp`` are not used alone because that
# would fabricate a specific issue without sufficient evidence.
ISSUE_RULES: tuple[IssueRule, ...] = (
    IssueRule("STITCHING_PROBLEM", r"\b(?:bung|tuột|đứt)\s+chỉ\b|\bđường\s+chỉ\s+(?:bị\s+)?(?:bung|tuột|đứt)\b"),
    IssueRule("SOLE_HARD", r"\bđế(?:\s+giày)?\b.{0,28}\b(?:hơi\s+|khá\s+)?cứng\b", ("giày", "dép", "sandal", "shoe", "footwear")),
    IssueRule("COMFORT_POOR", r"\b(?:đau\s+chân|đau\s+tai|đi\s+đau\s+chân)\b", ("giày", "dép", "sandal", "shoe", "footwear")),
    IssueRule("SIZE_TOO_SMALL", r"\bsize\b.{0,20}\b(?:hơi\s+|quá\s+)?chật\b|\b(?:hơi\s+|quá\s+)?chật\s+size\b"),
    IssueRule("SIZE_TOO_LARGE", r"\bsize\b.{0,20}\b(?:hơi\s+|quá\s+)?rộng\b|\b(?:hơi\s+|quá\s+)?rộng\s+size\b"),
    IssueRule("DELIVERY_DELAY", r"\b(?:giao(?:\s+hàng)?|ship(?:ping)?)\b.{0,30}\b(?:rất\s+|khá\s+|quá\s+)?(?:chậm|lâu|trễ)\b"),
    IssueRule("DELIVERY_FAST", r"\b(?:giao(?:\s+hàng)?|ship(?:ping)?)\b.{0,30}\b(?:rất\s+)?nhanh\b"),
    IssueRule("PACKAGING_DAMAGED", r"\b(?:hộp|đóng\s+gói|bao\s+bì)\b.{0,30}\b(?:bị\s+)?(?:móp|méo|rách)\b"),
    IssueRule("PACKAGING_POSITIVE", r"\b(?:hộp|đóng\s+gói|bao\s+bì)\b.{0,30}\b(?:kỹ|chắc\s+chắn|cẩn\s+thận)\b"),
    IssueRule("PRICE_HIGH", r"\bgiá(?:\s+cả)?\b.{0,24}\b(?:hơi\s+|quá\s+)?(?:cao|đắt|mắc)\b"),
    IssueRule("PRICE_POSITIVE", r"\bgiá(?:\s+cả)?\b.{0,24}\b(?:rẻ|hợp\s+lý|đáng\s+tiền)\b"),
    IssueRule("SELLER_SERVICE_NEGATIVE", r"\b(?:nhân\s+viên|shop|hỗ\s+trợ|cskh)\b.{0,36}\b(?:khó\s+chịu|thái\s+độ\s+kém|không\s+trả\s+lời|chậm\s+phản\s+hồi)\b", (), True),
    IssueRule("SELLER_SERVICE_POSITIVE", r"\b(?:nhân\s+viên|shop|hỗ\s+trợ|cskh)\b.{0,36}\b(?:nhiệt\s+tình|phản\s+hồi\s+nhanh|hỗ\s+trợ\s+nhanh)\b"),
)
