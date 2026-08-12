"""Central canonical-issue map adapted from ``nlp_engine.zip`` donor rules.

The map deliberately terminates at one of the project's six existing aspects;
canonical issues are explanatory sub-details, never new ABSA labels.
"""
from __future__ import annotations

from dataclasses import dataclass


CANONICAL_ISSUE_TO_ASPECT: dict[str, str] = {
    "PRODUCT_DEFECT": "product_quality",
    "PRODUCT_DAMAGED": "product_quality",
    "WRONG_PRODUCT": "product_quality",
    "WRONG_VARIANT": "product_quality",
    "MISSING_ITEM": "product_quality",
    "POOR_QUALITY": "product_quality",
    "NOT_AS_DESCRIBED": "product_quality",
    "USAGE_PROBLEM": "product_quality",
    "STITCHING_PROBLEM": "product_quality",
    "SOLE_HARD": "product_quality",
    "COMFORT_POOR": "product_quality",
    "SIZE_TOO_SMALL": "product_quality",
    "SIZE_TOO_LARGE": "product_quality",
    "DELIVERY_DELAY": "delivery",
    "DELIVERY_LOST": "delivery",
    "DELIVERY_WRONG": "delivery",
    "DELIVERY_FAILED": "delivery",
    "DELIVERY_BEHAVIOR": "delivery",
    "DELIVERY_DAMAGE": "delivery",
    "DELIVERY_FAST": "delivery",
    "PACKAGING_DAMAGED": "packaging",
    "PACKAGING_POOR": "packaging",
    "PACKAGING_OPENED": "packaging",
    "PACKAGING_PROTECTION": "packaging",
    "PACKAGING_POSITIVE": "packaging",
    "PRICE_HIGH": "price",
    "PRICE_CHANGED": "price",
    "VOUCHER_PROBLEM": "price",
    "PROMOTION_PROBLEM": "price",
    "VALUE_FOR_MONEY": "price",
    "PRICE_POSITIVE": "price",
    "SELLER_SERVICE_NEGATIVE": "customer_service",
    "SERVICE_NO_RESPONSE": "customer_service",
    "SERVICE_SLOW_RESPONSE": "customer_service",
    "SERVICE_RUDE": "customer_service",
    "SERVICE_POOR_RESOLUTION": "customer_service",
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
    IssueRule("PRODUCT_DEFECT", r"\b(?:bị\s+lỗi|hỏng)\b"),
    IssueRule("PRODUCT_DEFECT", r"\bkhông\s+(?:bật|lên\s+nguồn|hoạt\s+động)\b", (), True),
    IssueRule("PRODUCT_DAMAGED", r"\b(?:sản\s+phẩm|hàng)\b.{0,24}\b(?:bị\s+)?(?:vỡ|méo|nứt|hư)\b"),
    IssueRule("WRONG_PRODUCT", r"\b(?:gửi|giao)\b.{0,24}\bsai\s+(?:sản\s+phẩm|hàng|mẫu)\b"),
    IssueRule("WRONG_VARIANT", r"\b(?:gửi|giao)\b.{0,24}\bsai\s+(?:màu|size|kích\s+cỡ|phiên\s+bản)\b"),
    IssueRule("MISSING_ITEM", r"\bthiếu\s+(?:phụ\s+kiện|sản\s+phẩm|món|đồ)\b"),
    IssueRule("NOT_AS_DESCRIBED", r"\bkhông\s+giống\s+(?:mô\s+tả|ảnh)\b", (), True),
    IssueRule("POOR_QUALITY", r"\bchất\s+lượng\b.{0,18}\b(?:tệ|kém)\b"),
    IssueRule("USAGE_PROBLEM", r"\bkhông\s+dùng\s+được\b", (), True),
    IssueRule("STITCHING_PROBLEM", r"\b(?:bung|tuột|đứt)\s+chỉ\b|\bđường\s+chỉ\s+(?:bị\s+)?(?:bung|tuột|đứt)\b"),
    IssueRule("SOLE_HARD", r"\bđế(?:\s+giày)?\b.{0,28}\b(?:hơi\s+|khá\s+)?cứng\b", ("giày", "dép", "sandal", "shoe", "footwear")),
    IssueRule("COMFORT_POOR", r"\b(?:đau\s+chân|đau\s+tai|đi\s+đau\s+chân)\b", ("giày", "dép", "sandal", "shoe", "footwear")),
    IssueRule("SIZE_TOO_SMALL", r"\bsize\b.{0,20}\b(?:hơi\s+|quá\s+)?chật\b|\b(?:hơi\s+|quá\s+)?chật\s+size\b"),
    IssueRule("SIZE_TOO_LARGE", r"\bsize\b.{0,20}\b(?:hơi\s+|quá\s+)?rộng\b|\b(?:hơi\s+|quá\s+)?rộng\s+size\b"),
    IssueRule("DELIVERY_DELAY", r"\b(?:giao(?:\s+hàng)?|ship(?:ping)?)\b.{0,30}\b(?:rất\s+|khá\s+|quá\s+)?(?:chậm|lâu|trễ)\b"),
    IssueRule("DELIVERY_LOST", r"\b(?:không\s+nhận\s+được\s+hàng|thất\s+lạc)\b", (), True),
    IssueRule("DELIVERY_WRONG", r"\b(?:giao|ship)\b.{0,24}\bnhầm\s+(?:địa\s+chỉ|người\s+nhận)\b"),
    IssueRule("DELIVERY_FAILED", r"\b(?:giao\s+không\s+thành\s+công|không\s+giao\s+được)\b", (), True),
    IssueRule("DELIVERY_BEHAVIOR", r"\bshipper\b.{0,24}\b(?:khó\s+chịu|thô\s+lỗ|không\s+lịch\s+sự)\b"),
    IssueRule("DELIVERY_DAMAGE", r"\b(?:vận\s+chuyển|giao\s+hàng)\b.{0,28}\b(?:làm\s+)?(?:vỡ|móp|hỏng)\b"),
    IssueRule("DELIVERY_FAST", r"\b(?:giao(?:\s+hàng)?|ship(?:ping)?)\b.{0,30}\b(?:rất\s+)?nhanh\b"),
    IssueRule("PACKAGING_DAMAGED", r"\b(?:hộp|đóng\s+gói|bao\s+bì)\b.{0,30}\b(?:bị\s+)?(?:móp|méo|rách)\b"),
    IssueRule("PACKAGING_POOR", r"\b(?:đóng\s+gói|gói\s+hàng)\b.{0,24}\b(?:sơ\s+sài|cẩu\s+thả)\b"),
    IssueRule("PACKAGING_OPENED", r"\b(?:hộp|bao\s+bì)\b.{0,24}\b(?:bị\s+)?(?:mở|bóc)\b"),
    IssueRule("PACKAGING_PROTECTION", r"\b(?:không\s+có|thiếu)\s+(?:chống\s+sốc|bọc\s+lót)\b", (), True),
    IssueRule("PACKAGING_POSITIVE", r"\b(?:hộp|đóng\s+gói|bao\s+bì)\b.{0,30}\b(?:kỹ|chắc\s+chắn|cẩn\s+thận)\b"),
    IssueRule("PRICE_HIGH", r"\bgiá(?:\s+cả)?\b.{0,24}\b(?:hơi\s+|quá\s+)?(?:cao|đắt|mắc)\b"),
    IssueRule("PRICE_CHANGED", r"\bgiá\b.{0,28}\b(?:khác|thay\s+đổi)\b.{0,28}\b(?:lúc|khi)\b"),
    IssueRule("VOUCHER_PROBLEM", r"\b(?:không\s+dùng\s+được|không\s+áp\s+được)\s+voucher\b", (), True),
    IssueRule("PROMOTION_PROBLEM", r"\b(?:khuyến\s+mãi|ưu\s+đãi)\b.{0,24}\b(?:không\s+đúng|không\s+áp\s+dụng)\b"),
    IssueRule("VALUE_FOR_MONEY", r"\b(?:đáng\s+tiền|xứng\s+đáng)\b"),
    IssueRule("PRICE_POSITIVE", r"\bgiá(?:\s+cả)?\b.{0,24}\b(?:rẻ|hợp\s+lý|đáng\s+tiền)\b"),
    IssueRule("SELLER_SERVICE_NEGATIVE", r"\b(?:nhân\s+viên|shop|hỗ\s+trợ|cskh)\b.{0,36}\b(?:khó\s+chịu|thái\s+độ\s+kém|không\s+trả\s+lời|chậm\s+phản\s+hồi)\b", (), True),
    IssueRule("SERVICE_NO_RESPONSE", r"\b(?:nhắn|liên\s+hệ).{0,24}\bkhông\s+trả\s+lời\b", (), True),
    IssueRule("SERVICE_SLOW_RESPONSE", r"\b(?:phản\s+hồi|trả\s+lời)\b.{0,18}\b(?:rất\s+|quá\s+)?chậm\b"),
    IssueRule("SERVICE_RUDE", r"\b(?:nhân\s+viên|shop|hỗ\s+trợ)\b.{0,24}\b(?:khó\s+chịu|thô\s+lỗ)\b"),
    IssueRule("SERVICE_POOR_RESOLUTION", r"\b(?:không\s+giải\s+quyết|xử\s+lý\s+không\s+thỏa\s+đáng)\b", (), True),
    IssueRule("SELLER_SERVICE_POSITIVE", r"\b(?:nhân\s+viên|shop|hỗ\s+trợ|cskh)\b.{0,36}\b(?:nhiệt\s+tình|phản\s+hồi\s+nhanh|hỗ\s+trợ\s+nhanh)\b"),
)
