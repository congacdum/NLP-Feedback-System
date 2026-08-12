from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nlp.preprocessing.text import normalized_hash_text
from nlp.schema import ASPECTS, SENTIMENTS

TARGET_BY_SENTIMENT = {"positive": 120, "negative": 120, "neutral": 72, "mixed": 48}
TARGET_NO_ASPECT_RECORDS = 120


def read_jsonl(path: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSONL in {path}: {exc}") from exc


def norm_hash(text: str) -> str:
    normalized = normalized_hash_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the controlled ABSA balanced test set.")
    parser.add_argument("test", type=Path, help="Candidate or reviewed balanced-test JSONL")
    parser.add_argument("--against", type=Path, action="append", default=[], help="JSONL split that must not share exact text")
    parser.add_argument("--allow-incomplete", action="store_true", help="Check structure/leakage without enforcing the 2,160-annotation target")
    args = parser.parse_args()

    rows = read_jsonl(args.test)
    errors: list[str] = []
    ids: set[str] = set()
    texts: dict[str, str] = {}
    pair_counts: Counter[tuple[str, str]] = Counter()
    aspect_counts: Counter[str] = Counter()
    no_aspect_records = 0

    blocked_texts: dict[str, str] = {}
    for path in args.against:
        for row in read_jsonl(path):
            text = str(row.get("text") or "").strip()
            if text:
                blocked_texts[norm_hash(text)] = f"{path}:{row.get('id')}"

    for line_no, row in enumerate(rows, 1):
        record_id = str(row.get("id") or "").strip()
        text = str(row.get("text") or "").strip()
        if not record_id:
            errors.append(f"line {line_no}: missing id")
        elif record_id in ids:
            errors.append(f"line {line_no}: duplicate id {record_id}")
        ids.add(record_id)
        if not text:
            errors.append(f"line {line_no}: empty text")
            continue

        digest = norm_hash(text)
        if digest in texts:
            errors.append(f"line {line_no}: duplicate text with {texts[digest]}")
        else:
            texts[digest] = record_id
        if digest in blocked_texts:
            errors.append(f"line {line_no}: exact leakage with {blocked_texts[digest]}")
        if row.get("split") != "test_balanced":
            errors.append(f"line {line_no}: split must be test_balanced")

        seen_aspects: set[str] = set()
        annotations = row.get("annotations")
        if not isinstance(annotations, list):
            errors.append(f"line {line_no}: annotations must be a list")
            continue
        if not annotations:
            no_aspect_records += 1
        for annotation in annotations:
            aspect = annotation.get("aspect") if isinstance(annotation, dict) else None
            sentiment = annotation.get("sentiment") if isinstance(annotation, dict) else None
            if aspect not in ASPECTS:
                errors.append(f"line {line_no}: invalid aspect {aspect!r}")
                continue
            if sentiment not in SENTIMENTS:
                errors.append(f"line {line_no}: invalid sentiment {sentiment!r}")
                continue
            if aspect in seen_aspects:
                errors.append(f"line {line_no}: repeated aspect {aspect}")
                continue
            seen_aspects.add(aspect)
            aspect_counts[aspect] += 1
            pair_counts[(aspect, sentiment)] += 1

    if not args.allow_incomplete:
        for aspect in ASPECTS:
            for sentiment, expected in TARGET_BY_SENTIMENT.items():
                actual = pair_counts[(aspect, sentiment)]
                if actual != expected:
                    errors.append(f"quota: {aspect}/{sentiment} is {actual}, expected {expected}")
        if no_aspect_records != TARGET_NO_ASPECT_RECORDS:
            errors.append(f"quota: no_aspect records is {no_aspect_records}, expected {TARGET_NO_ASPECT_RECORDS}")

    report = {
        "file": str(args.test),
        "records": len(rows),
        "annotations": sum(aspect_counts.values()),
        "no_aspect_records": no_aspect_records,
        "aspect_counts": {aspect: aspect_counts[aspect] for aspect in ASPECTS},
        "aspect_sentiment_counts": {
            aspect: {sentiment: pair_counts[(aspect, sentiment)] for sentiment in SENTIMENTS}
            for aspect in ASPECTS
        },
        "target_per_aspect": sum(TARGET_BY_SENTIMENT.values()),
        "target_no_aspect_records": TARGET_NO_ASPECT_RECORDS,
        "leakage_comparison_files": [str(path) for path in args.against],
        "error_count": len(errors),
        "errors": errors[:100],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
