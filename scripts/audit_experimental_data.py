from __future__ import annotations

"""Audit only explicitly supplied Train/Dev ABSA splits.

The script intentionally has no default Test/Challenge paths.  It quantifies
data gaps before experimental augmentation; it does not label or alter data.
"""

import argparse
import itertools
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlp.preprocessing.text import normalized_hash_text
from nlp.schema import ASPECTS, SENTIMENTS

TOKEN_RE = re.compile(r"[\wÀ-ỹĐđ]+", re.UNICODE)
PATTERNS = {
    "price_negative_value": ("đắt", "chưa đáng tiền", "không xứng giá", "giá cao"),
    "price_positive_value": ("giá ổn", "hợp lý", "đáng tiền", "giá tốt"),
    "packaging_negative": ("hộp móp", "seal", "niêm phong", "rách", "bao bì"),
    "packaging_positive": ("đóng gói kỹ", "chống sốc", "bọc kỹ", "niêm phong chắc"),
}


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _split_report(rows: list[dict]) -> dict:
    aspect_counts = Counter(item["aspect"] for row in rows for item in row.get("annotations", []))
    sentiment = {aspect: Counter(item["sentiment"] for row in rows for item in row.get("annotations", []) if item["aspect"] == aspect) for aspect in ASPECTS}
    aspect_rows = {aspect: [row for row in rows if any(item["aspect"] == aspect for item in row.get("annotations", []))] for aspect in ASPECTS}
    multi = [row for row in rows if len(row.get("annotations", [])) > 1]
    pairs = Counter()
    for row in rows:
        present = sorted({item["aspect"] for item in row.get("annotations", [])})
        pairs.update(" + ".join(pair) for pair in itertools.combinations(present, 2))
    texts = [normalized_hash_text(row.get("text", "")) for row in rows]
    tokens = [token for text in texts for token in TOKEN_RE.findall(text)]
    pattern_counts = {name: sum(any(term in text.casefold() for term in terms) for text in texts) for name, terms in PATTERNS.items()}
    return {
        "rows": len(rows),
        "aspect_mentions": {aspect: aspect_counts[aspect] for aspect in ASPECTS},
        "sentiment_by_aspect": {aspect: {sent: sentiment[aspect][sent] for sent in SENTIMENTS} for aspect in ASPECTS},
        "single_aspect_rows": sum(len(row.get("annotations", [])) == 1 for row in rows),
        "multi_aspect_rows": len(multi),
        "no_aspect_rows": sum(not row.get("annotations", []) for row in rows),
        "multi_aspect_mentions_by_aspect": {aspect: sum(any(item["aspect"] == aspect for item in row.get("annotations", [])) for row in multi) for aspect in ASPECTS},
        "co_occurring_aspects": dict(pairs.most_common()),
        "average_review_tokens": round(sum(len(TOKEN_RE.findall(text)) for text in texts) / max(1, len(texts)), 3),
        "lexical_diversity": round(len(set(tokens)) / max(1, len(tokens)), 5),
        "source_distribution": dict(Counter(row.get("source", "missing") for row in rows)),
        "source_type_distribution": dict(Counter(row.get("source_type", row.get("source", "missing")) for row in rows)),
        "pattern_counts": pattern_counts,
        "exact_duplicate_count_within_split": len(texts) - len(set(texts)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Train/Dev data without opening held-out splits.")
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--dev", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    train, dev = _read(args.train), _read(args.dev)
    train_hashes = {normalized_hash_text(row.get("text", "")) for row in train}
    dev_hashes = {normalized_hash_text(row.get("text", "")) for row in dev}
    report = {
        "report_type": "train_dev_only_data_audit",
        "test_opened": False,
        "challenge_opened": False,
        "train": _split_report(train),
        "dev": _split_report(dev),
        "cross_split_exact_duplicates": len(train_hashes & dev_hashes),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
