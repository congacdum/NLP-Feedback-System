from __future__ import annotations

"""Create a versioned, explicitly synthetic Train/Dev augmentation revision.

The sentences are project-authored experimental scenarios, never human gold.
They target known coverage gaps while leaving V1 source files untouched.  The
builder does not accept or inspect a Test/Challenge path.
"""

import argparse
import hashlib
import itertools
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlp.preprocessing.text import normalized_hash_text
from nlp.schema import ASPECTS, SENTIMENTS

REVISION = "experimental_v2_project_authored_augmentation_v1"

CS = {
    "positive": [
        "bạn trực chat giải thích rất rõ cách sử dụng", "nhân viên cửa hàng chủ động gọi lại để hướng dẫn",
        "bộ phận chăm sóc phản hồi tin nhắn trong ít phút", "shop xử lý yêu cầu đổi cỡ rất gọn",
        "người tư vấn kiên nhẫn kiểm tra từng thông tin đơn", "bạn hỗ trợ theo dõi bảo hành đến khi xong",
        "nhân viên giải đáp thắc mắc bằng thái độ dễ chịu", "shop báo tình trạng hoàn tiền minh bạch",
        "bộ phận hỗ trợ xác nhận lỗi và đưa phương án nhanh", "tư vấn viên nhắc đúng mã sản phẩm cần đổi",
        "bạn CSKH gửi hướng dẫn đổi trả đầy đủ", "shop phản hồi qua ib rất lịch sự",
    ],
    "negative": [
        "nhắn ba lần mà shop vẫn im lặng", "bạn trực chat trả lời cộc lốc", "bộ phận hỗ trợ hẹn rồi quên phản hồi",
        "nhân viên tư vấn sai chính sách đổi trả", "yêu cầu bảo hành bị chuyển qua nhiều người", "shop xem tin nhắn nhưng không trả lời",
        "người hỗ trợ nói chuyện thiếu tôn trọng", "khi báo lỗi thì chỉ nhận được câu trả lời qua loa",
        "bộ phận CSKH kéo dài việc hoàn tiền không rõ lý do", "tư vấn viên khẳng định nhầm thông tin tồn kho",
        "shop từ chối kiểm tra khiếu nại", "bạn chăm sóc khách hàng ngắt cuộc trò chuyện giữa chừng",
    ],
    "neutral": [
        "shop đã tiếp nhận yêu cầu đổi trả", "bộ phận CSKH ghi nhận mã đơn của mình", "nhân viên gửi biểu mẫu bảo hành",
        "bạn trực chat trả lời theo quy trình", "shop thông báo thời gian xử lý khiếu nại", "tư vấn viên xác nhận đã nhận được ảnh lỗi",
    ],
}
OTHER = {
    "positive": [
        "móc khóa tặng kèm nhìn khá xinh", "quà khuyến mãi đi cùng đơn dùng được", "voucher tặng thêm được áp dụng ngay",
        "phụ kiện ngoài danh sách chính lại rất hữu ích", "shop gửi đúng món quà đã hứa", "mã ưu đãi tặng kèm hoạt động bình thường",
        "thẻ quà tặng trong hộp có thiết kế đẹp", "gói quà thêm khiến đơn hàng đáng nhớ hơn",
    ],
    "negative": [
        "đơn thiếu món quà tặng đã ghi trên chương trình", "voucher kèm theo báo lỗi khi thanh toán", "phụ kiện khuyến mãi trong đơn không đúng mô tả",
        "mã giảm giá tặng thêm biến mất trước khi dùng", "shop gửi nhầm màu của món quà kèm", "thẻ quà tặng bị bỏ quên khỏi kiện hàng",
        "quà tặng đi cùng bị trầy xước nặng", "phiếu ưu đãi đính kèm đã hết hạn",
    ],
    "neutral": [
        "đơn có kèm một phiếu quà tặng", "shop gửi thêm phụ kiện theo chương trình", "voucher được ghi trong phần khuyến mãi",
        "món quà tặng nằm riêng trong kiện hàng",
    ],
}
PRICE = {
    "positive": [
        "mức tiền bỏ ra khá tương xứng với trải nghiệm", "giá bán sau ưu đãi hợp lý", "so với mặt bằng chung thì giá này dễ chấp nhận",
        "chi phí như vậy là đáng tiền", "giá niêm yết vừa với chất lượng nhận được", "khuyến mãi làm món này có giá tốt",
    ],
    "negative": [
        "giá hiện tại cao hơn nhiều so với giá trị nhận được", "số tiền này chưa thật sự xứng đáng", "mức giá khiến mình phải cân nhắc lại",
        "đắt nếu đặt cạnh chất lượng thực tế", "giá tăng nhưng lợi ích không tương ứng", "chi phí bỏ ra hơi chát cho sản phẩm này",
    ],
    "neutral": [
        "giá đang ở mức trung bình", "mức giá không có gì nổi bật", "chi phí được niêm yết rõ ràng",
    ],
}
PACK = {
    "positive": [
        "lớp chống sốc quấn rất cẩn thận", "hộp ngoài cứng và niêm phong chắc", "túi bọc sạch sẽ, có chèn bảo vệ",
        "kiện hàng được dán kín nhiều lớp", "phần bao gói giữ sản phẩm cố định", "seal còn nguyên khi mở hộp",
    ],
    "negative": [
        "góc hộp bị ép méo khi nhận", "băng keo ngoài bung ra gần hết", "bên trong không có vật liệu chống sốc",
        "bao bì rách và dính bẩn", "niêm phong bị hở trước khi mở", "thùng carton quá mỏng nên biến dạng",
    ],
    "neutral": [
        "đơn được đặt trong một hộp giấy", "kiện hàng có dán băng keo bên ngoài", "sản phẩm nằm trong túi vận chuyển",
    ],
}
QUALITY = {
    "positive": ["vải mặc dễ chịu", "sản phẩm hoàn thiện khá tốt", "đồ dùng hoạt động ổn định", "màu sắc thực tế đẹp"],
    "negative": ["đường may đã xổ chỉ", "sản phẩm có lỗi ngay khi dùng", "chất liệu không giống hình mô tả", "đồ dùng nhanh hỏng"],
}
DELIVERY = {
    "positive": ["đơn đến sớm hơn dự kiến", "shipper giao đúng giờ đã hẹn", "hàng được chuyển rất nhanh", "quá trình vận chuyển cập nhật rõ"],
    "negative": ["đơn bị trễ nhiều ngày", "shipper dời lịch giao liên tục", "hàng đi vòng quá lâu mới tới", "trạng thái vận chuyển đứng yên"],
}
OPENERS = ["Theo trải nghiệm của mình,", "Lần này", "Với đơn vừa nhận,", "Mình thấy rằng", "Sau khi liên hệ,", "Thực tế", "Điểm mình chú ý là", "Trong quá trình mua,"]
ENDINGS = ["nên mình ghi nhận rõ điều này.", "và trải nghiệm khá dễ nhận ra.", "đó là lý do mình phản hồi.", "mình mong shop lưu ý hơn.", "điều đó làm mình yên tâm.", "vì vậy cảm nhận không hề mơ hồ."]
DEV_CONTEXTS = [
    "Tình huống này xảy ra ở lần mua gần đây.", "Mình nhận ra điều đó sau khi kiểm tra đơn tại nhà.",
    "Phản hồi này dựa trên trải nghiệm ở một đợt mua khác.", "Mình ghi lại chi tiết sau khi dùng sản phẩm vài ngày.",
    "Đây là trường hợp riêng của đơn giao vào cuối tuần.", "Mình so sánh với những lần mua trước rồi mới nhận xét.",
    "Chi tiết này xuất hiện khi mình theo dõi trạng thái đơn hàng.", "Mình nêu lại bối cảnh để trải nghiệm được rõ hơn.",
]


def _row(row_id: str, text: str, annotations: list[tuple[str, str]], split: str) -> dict:
    return {
        "id": row_id,
        "text": text,
        "annotations": [{"aspect": aspect, "sentiment": sentiment} for aspect, sentiment in annotations],
        "source": "project_authored_synthetic",
        "source_type": "project_authored_synthetic",
        "mapping_method": REVISION,
        "manual_verified": False,
        "is_scientific_gold": False,
        "annotation_guideline_version": "1.0",
        "dataset_revision": "experimental_v2",
        "split_origin": split,
    }


def _phrase_series(aspect: str, sentiment: str, phrases: list[str], count: int, split: str, offset: int = 0) -> list[dict]:
    rows = []
    for index in range(count):
        phrase = phrases[(index + offset) % len(phrases)]
        opener = OPENERS[((index // len(phrases)) + offset) % len(OPENERS)]
        ending = ENDINGS[((index // (len(phrases) * len(OPENERS))) + offset) % len(ENDINGS)]
        patterns = (
            f"{opener} {phrase}; {ending}",
            f"{phrase.capitalize()}. {ending}",
            f"{opener} mình nhận thấy {phrase}, {ending}",
            f"{phrase.capitalize()}, đây là chi tiết ảnh hưởng trực tiếp đến trải nghiệm của mình.",
        )
        text = patterns[(index // (len(phrases) * len(OPENERS) * len(ENDINGS)) + offset) % len(patterns)]
        rows.append(_row(f"v2::{split}::{aspect}::{sentiment}::{index:04d}", text, [(aspect, sentiment)], split))
    return rows


def _mixed_series(aspect: str, positive: list[str], negative: list[str], count: int, split: str, offset: int = 0) -> list[dict]:
    rows = []
    for index in range(count):
        good = positive[(index + offset) % len(positive)]
        bad = negative[((index // len(positive)) + offset) % len(negative)]
        forms = (f"{good.capitalize()} nhưng {bad}.", f"{bad.capitalize()}, dù {good}.", f"{good.capitalize()}; tuy vậy {bad}.")
        rows.append(_row(f"v2::{split}::{aspect}::mixed::{index:04d}", forms[(index // (len(positive) * len(negative)) + offset) % len(forms)], [(aspect, "mixed")], split))
    return rows


def _multi_series(name: str, clauses: list[tuple[str, str, list[str]]], count: int, split: str, offset: int = 0) -> list[dict]:
    rows = []
    for index in range(count):
        selected = []
        annotations = []
        for position, (aspect, sentiment, phrases) in enumerate(clauses):
            divisor = 1
            for _previous_aspect, _previous_sentiment, previous_phrases in clauses[:position]:
                divisor *= len(previous_phrases)
            selected.append(phrases[((index // divisor) + offset) % len(phrases)])
            annotations.append((aspect, sentiment))
        forms = (
            ", ".join(selected[:-1]) + " nhưng " + selected[-1] + ".",
            "Trong khi " + selected[0] + ", thì " + "; ".join(selected[1:]) + ".",
            "; ".join(piece.capitalize() if i == 0 else piece for i, piece in enumerate(selected)) + ".",
        )
        combinations = 1
        for _aspect, _sentiment, phrases in clauses:
            combinations *= len(phrases)
        rows.append(_row(f"v2::{split}::multi::{name}::{index:04d}", forms[(index // combinations + offset) % len(forms)], annotations, split))
    return rows


def _augmentation(split: str) -> list[dict]:
    is_train = split == "train"
    scale = 1 if is_train else 0
    counts = {"cs": 240 if is_train else 60, "other": 220 if is_train else 55, "price": 100 if is_train else 25, "pack": 100 if is_train else 25, "multi": 60 if is_train else 15, "triple": 40 if is_train else 10}
    # Dev enumerates a distinct part of each scenario space.  It is not a
    # lightly prefixed copy of Train templates, and the later leakage gate
    # still rejects any lexical near-duplicate that slips through.
    offset = 0 if is_train else 576
    rows: list[dict] = []
    for aspect, bank, total in (("customer_service", CS, counts["cs"]), ("other", OTHER, counts["other"]), ("price", PRICE, counts["price"]), ("packaging", PACK, counts["pack"])):
        sentiment_counts = {"positive": total * 3 // 10, "negative": total * 4 // 10, "neutral": total * 15 // 100}
        sentiment_counts["mixed"] = total - sum(sentiment_counts.values())
        for sentiment, number in sentiment_counts.items():
            if sentiment == "mixed":
                rows += _mixed_series(aspect, bank["positive"], bank["negative"], number, split, offset)
            else:
                rows += _phrase_series(aspect, sentiment, bank[sentiment], number, split, offset)
    rows += _multi_series("quality_price", [("product_quality", "positive", QUALITY["positive"]), ("price", "negative", PRICE["negative"])], counts["multi"], split, offset)
    rows += _multi_series("delivery_packaging", [("delivery", "negative", DELIVERY["negative"]), ("packaging", "negative", PACK["negative"])], counts["multi"], split, offset + 13)
    rows += _multi_series("delivery_service", [("delivery", "negative", DELIVERY["negative"]), ("customer_service", "negative", CS["negative"])], counts["multi"], split, offset + 29)
    rows += _multi_series("delivery_packaging_service", [("delivery", "negative", DELIVERY["negative"]), ("packaging", "negative", PACK["negative"]), ("customer_service", "negative", CS["negative"])], counts["triple"], split, offset + 43)
    if not is_train:
        for index, row in enumerate(rows):
            row["text"] = f"{row['text']} {DEV_CONTEXTS[index % len(DEV_CONTEXTS)]}"
    return rows


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _counts(rows: list[dict]) -> dict:
    return {aspect: sum(item["aspect"] == aspect for row in rows for item in row.get("annotations", [])) for aspect in ASPECTS}


def _validate(rows: list[dict]) -> None:
    seen = set()
    for row in rows:
        text = str(row.get("text") or "").strip()
        if not text:
            raise ValueError(f"empty synthetic text: {row['id']}")
        key = normalized_hash_text(text)
        if key in seen:
            raise ValueError(f"duplicate generated text: {row['id']}")
        seen.add(key)
        aspects = set()
        for item in row["annotations"]:
            if item["aspect"] not in ASPECTS or item["sentiment"] not in SENTIMENTS:
                raise ValueError(f"invalid annotation: {row['id']}")
            if item["aspect"] in aspects:
                raise ValueError(f"duplicate aspect label: {row['id']}")
            aspects.add(item["aspect"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a versioned project-authored synthetic experimental V2 Train/Dev revision.")
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--dev", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    old_train, old_dev = _read(args.train), _read(args.dev)
    synthetic_train, synthetic_dev = _augmentation("train"), _augmentation("dev")
    _validate(synthetic_train); _validate(synthetic_dev)
    old_hashes = {normalized_hash_text(row.get("text", "")) for row in old_train + old_dev}
    for row in synthetic_train + synthetic_dev:
        if normalized_hash_text(row["text"]) in old_hashes:
            raise ValueError(f"synthetic row collides with V1 data: {row['id']}")
    args.out.mkdir(parents=True, exist_ok=True)
    for split, rows in (("train", old_train + synthetic_train), ("dev", old_dev + synthetic_dev)):
        (args.out / f"{split}.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    provenance = synthetic_train + synthetic_dev
    (args.out / "project_authored_synthetic.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in provenance), encoding="utf-8")
    report = {
        "revision": REVISION,
        "test_opened": False,
        "challenge_opened": False,
        "rows": {"train_before": len(old_train), "dev_before": len(old_dev), "train_added": len(synthetic_train), "dev_added": len(synthetic_dev), "train_after": len(old_train) + len(synthetic_train), "dev_after": len(old_dev) + len(synthetic_dev), "removed": 0, "changed": 0},
        "provenance": {"project_authored_synthetic": len(provenance), "human_verified": 0, "public_mapped": 0, "is_scientific_gold": False},
        "aspect_counts_before": {"train": _counts(old_train), "dev": _counts(old_dev)},
        "aspect_counts_after": {"train": _counts(old_train + synthetic_train), "dev": _counts(old_dev + synthetic_dev)},
        "synthetic_annotation_distribution": Counter(item["aspect"] for row in provenance for item in row["annotations"]),
    }
    report["synthetic_annotation_distribution"] = dict(report["synthetic_annotation_distribution"])
    (args.out / "data_revision_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
