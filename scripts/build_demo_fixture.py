from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "nlp" / "data" / "demo"
CHALLENGE = ROOT / "nlp" / "data" / "challenge"

PHRASES = {
    "product_quality": {
        "positive": [
            "Chất vải mềm và mặc rất thoải mái.",
            "Sản phẩm chắc chắn, hoàn thiện tốt.",
            "Màu thực tế đẹp và đúng mô tả.",
            "Dùng vài tuần vẫn hoạt động ổn định.",
            "Đường may gọn, chất liệu tốt.",
            "Hàng nhận được đúng hình và đúng kích thước.",
            "Sản phẩm bền hơn mình mong đợi.",
            "Form đẹp, chất lượng hoàn thiện rất ổn.",
        ],
        "neutral": [
            "Chất lượng ở mức bình thường.",
            "Sản phẩm dùng được, không có gì nổi bật.",
            "Chất liệu tạm ổn so với nhu cầu.",
            "Màu sắc và kiểu dáng khá bình thường.",
            "Dùng ổn, chưa thấy ưu nhược điểm rõ ràng.",
            "Chất lượng đúng mức mình dự đoán.",
        ],
        "negative": [
            "Mới dùng hai hôm đã hỏng.",
            "Đường may ẩu và bị bung chỉ.",
            "Màu thực tế khác xa hình quảng cáo.",
            "Chất liệu mỏng và khá kém.",
            "Sản phẩm lỗi ngay lần đầu sử dụng.",
            "Kích thước sai so với mô tả.",
            "Hàng ọp ẹp, hoàn thiện rất tệ.",
            "Dùng chưa lâu đã xuống cấp rõ rệt.",
        ],
        "mixed": [
            "Vải mềm nhưng đường may rất ẩu.",
            "Thiết kế đẹp nhưng chất liệu khá mỏng.",
            "Màu đẹp nhưng sản phẩm hoàn thiện chưa tốt.",
            "Dùng ổn nhưng phần khóa lại rất dễ hỏng.",
            "Form đẹp nhưng đường chỉ thừa nhiều.",
            "Chất liệu tốt nhưng kích thước lại sai mô tả.",
        ],
    },
    "delivery": {
        "positive": [
            "Giao hàng rất nhanh.",
            "Đặt hôm qua hôm nay đã nhận được.",
            "Shipper giao đúng hẹn và lịch sự.",
            "Thời gian vận chuyển nhanh hơn dự kiến.",
            "Hàng tới sớm và không bị thất lạc.",
            "Quá trình giao nhận rất thuận lợi.",
        ],
        "neutral": [
            "Thời gian giao hàng bình thường.",
            "Giao đúng khoảng thời gian dự kiến.",
            "Vận chuyển không nhanh cũng không chậm.",
            "Khâu giao nhận ở mức bình thường.",
            "Hàng đến đúng ngày dự kiến.",
        ],
        "negative": [
            "Giao hàng quá chậm.",
            "Đặt cả tuần mới nhận được.",
            "Shipper hẹn nhiều lần nhưng không giao.",
            "Đơn bị trễ lâu hơn dự kiến.",
            "Vận chuyển lâu và cập nhật trạng thái không rõ.",
            "Hàng bị thất lạc rồi mới giao lại.",
            "Chờ mãi mới thấy hàng tới.",
        ],
        "mixed": [
            "Shipper lịch sự nhưng giao trễ nhiều ngày.",
            "Hàng đến nguyên vẹn nhưng thời gian vận chuyển quá lâu.",
            "Giao đúng địa chỉ nhưng bị trễ so với hẹn.",
            "Cập nhật vận chuyển rõ nhưng hàng tới chậm.",
        ],
    },
    "customer_service": {
        "positive": [
            "Shop tư vấn rất nhiệt tình.",
            "Nhân viên hỗ trợ nhanh và dễ chịu.",
            "Shop trả lời tin nhắn rất nhanh.",
            "Đổi trả được hỗ trợ rõ ràng.",
            "Khiếu nại được xử lý nhanh chóng.",
            "Shop giải thích và hỗ trợ rất có trách nhiệm.",
        ],
        "neutral": [
            "Shop phản hồi ở mức bình thường.",
            "Tư vấn đủ thông tin cơ bản.",
            "Dịch vụ hỗ trợ không có gì đặc biệt.",
            "Nhân viên trả lời đúng câu hỏi.",
            "Khâu chăm sóc khách hàng khá bình thường.",
        ],
        "negative": [
            "Shop trả lời rất chậm.",
            "Nhân viên tư vấn khó chịu.",
            "Yêu cầu đổi trả nhưng shop không hỗ trợ.",
            "Khiếu nại nhiều lần vẫn không được giải quyết.",
            "Shop né tránh khi mình báo sản phẩm lỗi.",
            "Hỗ trợ sau bán rất tệ.",
        ],
        "mixed": [
            "Shop tư vấn nhiệt tình nhưng xử lý đổi trả quá chậm.",
            "Nhân viên trả lời nhanh nhưng giải quyết vấn đề chưa thỏa đáng.",
            "Lúc mua tư vấn tốt nhưng sau bán hỗ trợ kém.",
            "Shop nói chuyện lịch sự nhưng hoàn tiền quá lâu.",
        ],
    },
    "packaging": {
        "positive": [
            "Đóng gói rất cẩn thận.",
            "Hộp chắc chắn và có chống sốc đầy đủ.",
            "Gói hàng kỹ, sản phẩm được bảo vệ tốt.",
            "Bao bì sạch đẹp và niêm phong chắc.",
            "Đóng kiện cẩn thận nên hàng không bị va đập.",
            "Phần đóng gói rất chỉn chu.",
        ],
        "neutral": [
            "Đóng gói ở mức bình thường.",
            "Bao bì đủ dùng, không có gì đặc biệt.",
            "Hộp sản phẩm bình thường.",
            "Khâu đóng gói tạm ổn.",
            "Gói hàng đúng mức cơ bản.",
        ],
        "negative": [
            "Đóng gói quá sơ sài.",
            "Hộp móp nặng khi nhận.",
            "Không có chống sốc nên sản phẩm bị va đập.",
            "Bao bì rách và niêm phong lỏng lẻo.",
            "Gói hàng cẩu thả.",
            "Hộp bên ngoài bị nát.",
        ],
        "mixed": [
            "Bọc chống sốc kỹ nhưng hộp bên ngoài bị móp.",
            "Niêm phong chắc nhưng bao bì khá xấu.",
            "Gói nhiều lớp nhưng hộp vẫn bị rách.",
            "Đóng gói sạch nhưng phần chống va đập chưa tốt.",
        ],
    },
    "price": {
        "positive": [
            "Giá rất hợp lý.",
            "Mức giá này khá đáng tiền.",
            "Giá rẻ so với chất lượng nhận được.",
            "Mua lúc giảm giá nên rất hời.",
            "Sản phẩm có giá tốt trong tầm tiền.",
            "Chi phí bỏ ra hoàn toàn xứng đáng.",
        ],
        "neutral": [
            "Giá ở mức bình thường.",
            "Mức giá không rẻ cũng không đắt.",
            "Giá tương đương các sản phẩm khác.",
            "Chi phí ở mức chấp nhận được.",
            "Giá không có gì đặc biệt.",
        ],
        "negative": [
            "Giá quá cao.",
            "Không đáng tiền với chất lượng này.",
            "Sản phẩm khá đắt so với mặt bằng chung.",
            "Mức giá này cao hơn mình kỳ vọng.",
            "Giá cao nhưng chất lượng không tương xứng.",
            "Không có khuyến mãi nên mua khá chát.",
        ],
        "mixed": [
            "Giá niêm yết cao nhưng lúc giảm giá thì khá hợp lý.",
            "Hơi đắt nhưng vẫn đáng tiền.",
            "Giá cao hơn mong đợi nhưng chất lượng phần nào xứng đáng.",
            "Không rẻ nhưng xét tổng thể vẫn chấp nhận được.",
        ],
    },
    "other": {
        "positive": [
            "Shop tặng thêm móc khóa, mình khá thích.",
            "Có quà tặng kèm rất dễ thương.",
            "Thiệp cảm ơn đi kèm tạo cảm giác khá vui.",
            "Có thêm quà nhỏ ngoài mong đợi.",
            "Chương trình tặng quà kèm rất thú vị.",
        ],
        "neutral": [
            "Có kèm một tờ hướng dẫn chung.",
            "Đơn hàng có thêm quà tặng nhỏ.",
            "Có thiệp cảm ơn đi kèm.",
            "Có phụ kiện tặng kèm như thông báo.",
        ],
        "negative": [
            "Quà tặng ghi trong chương trình nhưng lại không có.",
            "Thiếu phụ kiện tặng kèm đã thông báo.",
            "Quà tặng kèm bị thiếu.",
            "Chương trình tặng quà không đúng như giới thiệu.",
        ],
        "mixed": [
            "Quà tặng đẹp nhưng lại thiếu một món như thông báo.",
            "Có quà kèm nhưng không đúng loại đã giới thiệu.",
            "Thiệp đẹp nhưng phụ kiện tặng kèm lại thiếu.",
        ],
    },
}

PREFIXES = ["", "Mình thấy ", "Theo trải nghiệm của mình, ", "Thực tế thì "]
SUFFIXES = ["", " Nói chung là vậy.", " Đây là cảm nhận sau khi dùng."]


def record(idx: int, text: str, annotations: list[dict], split: str, group: str) -> dict:
    return {
        "id": f"demo_{idx:04d}",
        "text": text.strip(),
        "annotations": annotations,
        "split": split,
        "source": "project_demo_fixture",
        "group_id": group,
        "is_scientific_gold": False,
    }


def build() -> list[dict]:
    random.seed(20260809)
    rows: list[dict] = []
    idx = 1
    # Unique phrase-level split: phrase wording never appears across splits.
    for aspect, sentiments in PHRASES.items():
        for sentiment, phrases in sentiments.items():
            for p_idx, phrase in enumerate(phrases):
                split = "train" if p_idx < max(3, len(phrases) - 2) else ("dev" if p_idx == len(phrases)-2 else "test")
                prefix = PREFIXES[(p_idx + len(aspect)) % len(PREFIXES)]
                suffix = SUFFIXES[(p_idx + len(sentiment)) % len(SUFFIXES)]
                rows.append(record(idx, prefix + phrase[0].lower() + phrase[1:] + suffix, [{"aspect": aspect, "sentiment": sentiment}], split, f"single:{aspect}:{sentiment}:{p_idx}"))
                idx += 1

    # Multi-aspect examples, manually structured and split by exact scenario.
    combos = [
        ("Áo đẹp nhưng giao quá lâu.", [("product_quality","positive"),("delivery","negative")]),
        ("Đóng gói kỹ, ship nhanh nhưng giá hơi cao.", [("packaging","positive"),("delivery","positive"),("price","negative")]),
        ("Shop tư vấn nhiệt tình nhưng hàng bị lỗi.", [("customer_service","positive"),("product_quality","negative")]),
        ("Giá hợp lý và chất lượng khá tốt.", [("price","positive"),("product_quality","positive")]),
        ("Hàng ổn nhưng hộp móp và giao chậm.", [("product_quality","neutral"),("packaging","negative"),("delivery","negative")]),
        ("Shop trả lời chậm nhưng hỗ trợ đổi sản phẩm lỗi khá tốt.", [("customer_service","mixed"),("product_quality","negative")]),
        ("Sản phẩm đẹp, giá tốt, đóng gói cũng cẩn thận.", [("product_quality","positive"),("price","positive"),("packaging","positive")]),
        ("Giao đúng hẹn nhưng hộp rách.", [("delivery","positive"),("packaging","negative")]),
        ("Giá bình thường, shop tư vấn bình thường.", [("price","neutral"),("customer_service","neutral")]),
        ("Có quà tặng đẹp nhưng giao quá trễ.", [("other","positive"),("delivery","negative")]),
        ("Chất lượng tốt nhưng hơi đắt và shop rep chậm.", [("product_quality","positive"),("price","negative"),("customer_service","negative")]),
        ("Hộp đẹp, hàng đúng mô tả nhưng shipper thái độ khó chịu.", [("packaging","positive"),("product_quality","positive"),("delivery","negative")]),
        ("Đổi trả nhanh dù sản phẩm ban đầu bị lỗi.", [("customer_service","positive"),("product_quality","negative")]),
        ("Mức giá ổn nhưng đóng gói chỉ ở mức bình thường.", [("price","positive"),("packaging","neutral")]),
        ("Hàng tới sớm, tuy nhiên màu sắc không đúng ảnh.", [("delivery","positive"),("product_quality","negative")]),
        ("Shop lịch sự, giao nhanh, nhưng thiếu quà tặng đã hứa.", [("customer_service","positive"),("delivery","positive"),("other","negative")]),
        ("Đóng gói sơ sài nhưng may là sản phẩm vẫn tốt.", [("packaging","negative"),("product_quality","positive")]),
        ("Giá đắt, giao chậm và shop không phản hồi.", [("price","negative"),("delivery","negative"),("customer_service","negative")]),
    ]
    # repeat with meaning-preserving but visibly different connective variants; marked fixture only.
    connectors = ["", " Mình đánh giá như vậy.", " Trải nghiệm thực tế của mình là thế."]
    for rep in range(3):
        for c_idx, (text, anns) in enumerate(combos):
            # scenario-level split so exact base scenario remains in one split.
            split = "train" if c_idx < 12 else ("dev" if c_idx < 15 else "test")
            variant = text + connectors[rep]
            rows.append(record(idx, variant, [{"aspect": a, "sentiment": s} for a, s in anns], split, f"combo:{c_idx}"))
            idx += 1

    # no-aspect / invalid meaningfulness examples used to test status handling.
    no_aspect = [
        "okkkkk", ".....", "abc xyz", "👍👍👍", "mới nhận", "đã xem", "không biết nói gì", "12345"
    ]
    for j, text in enumerate(no_aspect):
        split = "train" if j < 5 else ("dev" if j == 5 else "test")
        rows.append(record(idx, text, [], split, f"noaspect:{j}")); idx += 1
    return rows


CHALLENGE_ROWS = [
    ("implicit", "Đặt từ tuần trước giờ mới thấy hàng.", [("delivery","negative")]),
    ("implicit", "Chờ dài cổ mới nhận được đơn.", [("delivery","negative")]),
    ("implicit", "Vừa đặt hôm qua sáng nay đã cầm trên tay.", [("delivery","positive")]),
    ("negation", "Không hề tệ như mình tưởng.", [("product_quality","positive")]),
    ("negation", "Không phải là không đáng tiền.", [("price","positive")]),
    ("negation", "Shop không hề bỏ mặc khi mình cần đổi hàng.", [("customer_service","positive")]),
    ("contrast", "Nhìn đẹp đấy nhưng dùng một hôm đã lỗi.", [("product_quality","mixed")]),
    ("contrast", "Shop nói chuyện dễ chịu nhưng xử lý hoàn tiền thì quá lâu.", [("customer_service","mixed")]),
    ("contrast", "Hộp đẹp nhưng chống sốc gần như không có.", [("packaging","mixed")]),
    ("multi_aspect", "Hàng đẹp, gói kỹ, mỗi tội tới quá muộn.", [("product_quality","positive"),("packaging","positive"),("delivery","negative")]),
    ("multi_aspect", "Shop rep nhanh, giá dễ chịu nhưng áo bị bung chỉ.", [("customer_service","positive"),("price","positive"),("product_quality","negative")]),
    ("multi_aspect", "Ship nhanh nhưng hộp móp và giá cũng hơi chát.", [("delivery","positive"),("packaging","negative"),("price","negative")]),
    ("mixed", "Vải xịn mà may thế này thì chịu, chỉ bung đầy áo.", [("product_quality","mixed")]),
    ("mixed", "Giá niêm yết cao thật nhưng săn sale thì lại khá hời.", [("price","mixed")]),
    ("mixed", "Shipper lịch sự nhưng cứ hẹn rồi trễ mãi.", [("delivery","mixed")]),
    ("slang", "sp oke phết nhưng shop rep lâu vãi.", [("product_quality","positive"),("customer_service","negative")]),
    ("slang", "ship nhanh vl, hàng cũng xịn.", [("delivery","positive"),("product_quality","positive")]),
    ("slang", "giá chát quá trời, bù lại đồ ngon.", [("price","negative"),("product_quality","positive")]),
    ("no_accent", "giao hang cham qua, doi mai moi toi", [("delivery","negative")]),
    ("no_accent", "shop rep nhanh va tu van rat ok", [("customer_service","positive")]),
    ("no_accent", "dong goi can than nhung gia hoi cao", [("packaging","positive"),("price","negative")]),
    ("sarcasm", "Giao nhanh ghê, có mỗi mười ngày thôi.", [("delivery","negative")]),
    ("sarcasm", "Đóng gói cẩn thận quá, hộp nát luôn rồi.", [("packaging","negative")]),
    ("sarcasm", "Shop hỗ trợ nhiệt tình thật, nhắn ba ngày không thấy trả lời.", [("customer_service","negative")]),
    ("noise", "okkkkkkkkk", []),
    ("noise", ".....", []),
    ("noise", "👍", []),
    ("neutral", "Giá cũng bình thường, không rẻ không đắt.", [("price","neutral")]),
    ("neutral", "Thời gian giao đúng như dự kiến.", [("delivery","neutral")]),
    ("other", "Có thêm một tấm thiệp cảm ơn khá dễ thương.", [("other","positive")]),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    CHALLENGE.mkdir(parents=True, exist_ok=True)
    rows = build()
    all_path = OUT / "demo_absa.jsonl"
    with all_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    for split in ("train", "dev", "test"):
        with (OUT / f"{split}.jsonl").open("w", encoding="utf-8") as f:
            for row in rows:
                if row["split"] == split:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (CHALLENGE / "demo_challenge.jsonl").open("w", encoding="utf-8") as f:
        for i, (kind, text, anns) in enumerate(CHALLENGE_ROWS, 1):
            f.write(json.dumps({
                "id": f"challenge_{i:03d}",
                "slice": kind,
                "text": text,
                "annotations": [{"aspect": a, "sentiment": s} for a, s in anns],
                "source": "project_demo_challenge_fixture",
                "is_scientific_gold": False,
            }, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} demo records and {len(CHALLENGE_ROWS)} challenge records")


if __name__ == "__main__":
    main()
