from __future__ import annotations

import re
from typing import Dict, List

from nlp.preprocessing.text import normalize_text
from nlp.schema import ASPECTS

KEYWORDS = {
    "product_quality": ["chất lượng", "chất liệu", "vải", "đường may", "bung chỉ", "hỏng", "lỗi", "màu", "form", "kích thước", "đúng hình", "sản phẩm", "sp", "hàng"],
    "delivery": ["giao", "ship", "shipper", "vận chuyển", "nhận được", "tới", "đến", "đơn", "chờ"],
    "customer_service": ["shop", "tư vấn", "hỗ trợ", "đổi trả", "hoàn tiền", "bảo hành", "nhân viên", "rep", "phản hồi", "khiếu nại"],
    "packaging": ["đóng gói", "gói hàng", "hộp", "bao bì", "chống sốc", "niêm phong", "bọc"],
    "price": ["giá", "đắt", "rẻ", "đáng tiền", "hời", "chát", "khuyến mãi", "sale"],
    "other": ["quà", "tặng kèm", "thiệp", "phụ kiện tặng"],
}
POS = ["đẹp", "tốt", "ổn", "nhanh", "kỹ", "cẩn thận", "hợp lý", "đáng tiền", "nhiệt tình", "lịch sự", "xịn", "thích", "hời"]
NEG = ["tệ", "chậm", "lâu", "hỏng", "lỗi", "ẩu", "móp", "rách", "đắt", "cao", "khó chịu", "không hỗ trợ", "thất lạc", "thiếu", "sơ sài"]
NEGATION = ["không", "chẳng", "chưa"]


def _simple_sentiment(text: str, aspect: str) -> str:
    lower = text.casefold()
    # Intentional baseline limitations retained for honest comparison.
    pos = sum(1 for w in POS if w in lower)
    neg = sum(1 for w in NEG if w in lower)
    if pos and neg:
        return "mixed"
    if neg:
        return "negative"
    if pos:
        return "positive"
    return "neutral"


class RuleABSA:
    model_version = "rule-baseline-v0"

    def analyze(self, text: str) -> dict:
        clean = normalize_text(text)
        lower = clean.casefold()
        aspects: List[dict] = []
        scores: Dict[str, float] = {}
        for aspect in ASPECTS:
            matches = [kw for kw in KEYWORDS[aspect] if kw in lower]
            score = min(0.95, 0.35 + 0.15 * len(matches)) if matches else 0.05
            scores[aspect] = score
            if matches:
                sentiment = _simple_sentiment(clean, aspect)
                aspects.append({
                    "aspect": aspect,
                    "sentiment": sentiment,
                    "aspect_score": score,
                    "sentiment_score": 0.55,
                })
        return {
            "text": clean,
            "status": "ok" if aspects else "no_aspect",
            "aspects": aspects,
            "aspect_scores": scores,
            "sentiment_by_aspect": {x["aspect"]: x["sentiment"] for x in aspects},
            "sentiment_scores": {},
            "model_version": self.model_version,
            "backend": "rule_baseline",
        }
