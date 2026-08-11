from __future__ import annotations

"""Produce a reproducible quality report for candidate, mapped, or gold ABSA JSONL."""

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(ROOT))

from nlp.preprocessing.text import normalized_hash_text
from nlp.schema import ASPECTS, SENTIMENTS


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def token_set(text: str) -> set[str]:
    return set(normalized_hash_text(text).split())


def near_duplicate_count(rows: list[tuple[str, dict]], *, threshold: float) -> int:
    """Conservative, bounded token-Jaccard check for review queues and reports.

    The strict Train/Dev/Test leakage gate remains ``check_dataset.py``.  This
    report deliberately caps comparisons so it stays usable for a large pool.
    """
    signatures: list[set[str]] = []
    count = 0
    for _, row in rows:
        current = token_set(str(row.get("text") or ""))
        if len(current) < 4:
            signatures.append(current)
            continue
        for previous in signatures:
            if len(previous) < 4 or not (current & previous):
                continue
            score = len(current & previous) / max(1, len(current | previous))
            if score >= threshold:
                count += 1
                break
        signatures.append(current)
    return count


def build_report(splits: dict[str, list[dict]], *, near_threshold: float) -> dict:
    all_rows = [(split, row) for split, rows in splits.items() for row in rows]
    sources = Counter()
    aspects = Counter()
    sentiments = Counter()
    pairs = Counter()
    lengths: list[int] = []
    exact_hashes: dict[str, list[str]] = {}
    no_aspect = mixed = multi_aspect = 0
    for split, row in all_rows:
        sources[str(row.get("source") or "unknown")] += 1
        text = str(row.get("text") or "")
        lengths.append(len(normalized_hash_text(text).split()))
        digest = normalized_hash_text(text)
        exact_hashes.setdefault(digest, []).append(f"{split}:{row.get('id', '')}")
        annotations = row.get("annotations") or []
        if not annotations:
            no_aspect += 1
        if len(annotations) > 1:
            multi_aspect += 1
        for annotation in annotations:
            aspect = annotation.get("aspect")
            sentiment = annotation.get("sentiment")
            if aspect in ASPECTS:
                aspects[aspect] += 1
            if sentiment in SENTIMENTS:
                sentiments[sentiment] += 1
            if aspect in ASPECTS and sentiment in SENTIMENTS:
                pairs[f"{aspect}#{sentiment}"] += 1
                if sentiment == "mixed":
                    mixed += 1
    duplicate_groups = {key: ids for key, ids in exact_hashes.items() if key and len(ids) > 1}
    near_rows = all_rows[:3000]
    return {
        "total_samples": len(all_rows),
        "split_counts": {name: len(rows) for name, rows in splits.items()},
        "source_distribution": dict(sorted(sources.items())),
        "aspect_distribution": {name: aspects[name] for name in ASPECTS},
        "sentiment_distribution": {name: sentiments[name] for name in SENTIMENTS},
        "aspect_sentiment": {f"{aspect}#{sentiment}": pairs[f"{aspect}#{sentiment}"] for aspect in ASPECTS for sentiment in SENTIMENTS},
        "multi_aspect_rate": (multi_aspect / len(all_rows)) if all_rows else 0.0,
        "mixed_annotation_count": mixed,
        "no_aspect_count": no_aspect,
        "review_length_tokens": {"min": min(lengths) if lengths else 0, "median": median(lengths) if lengths else 0, "mean": mean(lengths) if lengths else 0, "max": max(lengths) if lengths else 0},
        "duplicate_count": sum(len(ids) - 1 for ids in duplicate_groups.values()),
        "duplicate_groups": list(duplicate_groups.values())[:50],
        "near_duplicate_count": near_duplicate_count(near_rows, threshold=near_threshold),
        "near_duplicate_note": f"bounded token-Jaccard scan over first {len(near_rows)} rows; use check_dataset.py for strict cross-split leakage",
    }


def markdown(report: dict) -> str:
    lines = ["# NLP Data Quality Report", "", f"- Total samples: **{report['total_samples']}**", f"- Split counts: `{report['split_counts']}`", f"- No-aspect: **{report['no_aspect_count']}**", f"- Multi-aspect rate: **{report['multi_aspect_rate']:.2%}**", f"- Mixed annotations: **{report['mixed_annotation_count']}**", f"- Exact duplicate rows: **{report['duplicate_count']}**", f"- Near-duplicate candidates: **{report['near_duplicate_count']}**", "", "## Source distribution", ""]
    lines.extend(f"- {key}: {value}" for key, value in report["source_distribution"].items())
    lines.extend(["", "## Aspect × sentiment", "", "| Aspect | Positive | Neutral | Negative | Mixed |", "|---|---:|---:|---:|---:|"])
    for aspect in ASPECTS:
        lines.append("| " + aspect + " | " + " | ".join(str(report["aspect_sentiment"][f"{aspect}#{sentiment}"]) for sentiment in SENTIMENTS) + " |")
    lines.extend(["", "## Review length", "", f"`{report['review_length_tokens']}`", "", "> This report does not make data scientific gold. Run the strict gold assembly and leakage gates separately."])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Report ABSA data coverage, provenance, duplicates, and review lengths")
    parser.add_argument("--train", type=Path, default=ROOT / "nlp/data/gold/train.jsonl")
    parser.add_argument("--dev", type=Path, default=ROOT / "nlp/data/gold/dev.jsonl")
    parser.add_argument("--test", type=Path, default=ROOT / "nlp/data/gold/test.jsonl")
    parser.add_argument("--out-json", type=Path, default=ROOT / "nlp/data/gold/data_quality_report.json")
    parser.add_argument("--out-md", type=Path, default=ROOT / "nlp/data/gold/data_quality_report.md")
    parser.add_argument("--near-jaccard", type=float, default=0.92)
    args = parser.parse_args()
    splits = {"train": read_jsonl(args.train), "dev": read_jsonl(args.dev), "test": read_jsonl(args.test)}
    report = build_report(splits, near_threshold=args.near_jaccard)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.out_md.write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
