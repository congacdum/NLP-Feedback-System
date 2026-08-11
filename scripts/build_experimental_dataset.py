from __future__ import annotations

"""Build a technically valid, non-scientific ABSA dataset.

It exists solely to exercise model training while project-specific human gold is
still incomplete.  Public rows retain their conservative mapping provenance and
demo fixtures are retained only for missing project taxonomy coverage.  Never
pass this output to ``--scientific-final``.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(ROOT))

from nlp.preprocessing.text import normalized_hash_text
from nlp.schema import normalize_annotations


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def canonical(row: dict, split: str, origin: str) -> dict | None:
    text = str(row.get("text") or "").strip()
    if not text or not normalized_hash_text(text):
        return None
    annotations = [dict(aspect=item.aspect, sentiment=item.sentiment) for item in normalize_annotations(row.get("annotations") or [])]
    return {
        "id": f"experimental::{origin}::{row.get('id', '')}",
        "text": text,
        "annotations": annotations,
        "split": split,
        "source": str(row.get("source") or origin),
        "source_id": str(row.get("id") or ""),
        "original_labels": row.get("original_labels", row.get("annotations", [])),
        "mapping_method": "conservative_public_mapping" if origin == "public" else "project_demo_fixture",
        "manual_verified": False,
        "is_scientific_gold": False,
        "experimental_only": True,
    }


def labels(row: dict) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((item["aspect"], item["sentiment"]) for item in row["annotations"]))


def _features(normalized: str) -> list[str]:
    tokens = normalized.split()
    return tokens if len(tokens) < 2 else tokens + [f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)]


def _simhash64(normalized: str) -> int:
    vector = [0] * 64
    for feature in _features(normalized):
        value = int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(64):
            vector[bit] += 1 if (value >> bit) & 1 else -1
    return sum((1 << bit) for bit, value in enumerate(vector) if value >= 0)


def _shingles(normalized: str) -> set[str]:
    tokens = normalized.split()
    return set(tokens) if len(tokens) <= 2 else {" ".join(tokens[index:index + 2]) for index in range(len(tokens) - 1)}


def _jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, len(left | right))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a deduplicated EXPERIMENTAL ABSA Train/Dev/Test dataset; never scientific gold")
    parser.add_argument("--mapped", type=Path, default=ROOT / "nlp/data/mapped")
    parser.add_argument("--demo", type=Path, default=ROOT / "nlp/data/demo")
    parser.add_argument("--out", type=Path, default=ROOT / "nlp/data/experimental")
    args = parser.parse_args()

    input_rows: dict[str, list[dict]] = {"train": [], "dev": [], "test": []}
    report: dict = {"artifact_kind": "experimental_dataset", "scientific_final": False, "policy": {"unsafe_mapped_rows_excluded": True, "demo_fixture_included_for_taxonomy_coverage": True, "cross_split_dedup_priority": ["test", "dev", "train"]}, "inputs": {}, "excluded": Counter(), "deduplicated": Counter()}
    for split in input_rows:
        mapped = read_jsonl(args.mapped / f"{split}.jsonl")
        demo = read_jsonl(args.demo / f"{split}.jsonl")
        report["inputs"][split] = {"mapped": len(mapped), "demo": len(demo)}
        for row in mapped:
            if row.get("safe_for_auto_gold") is not True or row.get("requires_manual_review"):
                report["excluded"]["unsafe_or_ambiguous_public"] += 1
                continue
            item = canonical(row, split, "public")
            if item:
                input_rows[split].append(item)
        for row in demo:
            item = canonical(row, split, "demo")
            if item:
                input_rows[split].append(item)

    # Prefer unique held-out examples, then Dev, then Train. Any conflicting
    # duplicate is excluded rather than silently relabelled.
    seen: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {}
    near_index: dict[tuple[int, int], list[tuple[int, set[str]]]] = {}
    output: dict[str, list[dict]] = {"train": [], "dev": [], "test": []}
    for split in ("test", "dev", "train"):
        local: dict[str, dict] = {}
        for row in input_rows[split]:
            digest = normalized_hash_text(row["text"])
            if digest in local:
                if labels(local[digest]) != labels(row):
                    report["excluded"]["same_split_conflicting_duplicate"] += 1
                    local.pop(digest, None)
                else:
                    report["deduplicated"][f"same_split_{split}"] += 1
                continue
            local[digest] = row
        for digest, row in local.items():
            if digest in seen:
                prior_split, prior_labels = seen[digest]
                key = "cross_split_conflicting_duplicate" if prior_labels != labels(row) else "cross_split_duplicate"
                report["excluded"][key] += 1
                continue
            # Same conservative SimHash + bigram-Jaccard leakage rule used by
            # check_dataset.py. Higher-priority held-out rows are retained.
            if len(digest.split()) >= 5:
                simhash = _simhash64(digest)
                shingles = _shingles(digest)
                near = False
                for band in range(4):
                    for other_hash, other_shingles in near_index.get((band, (simhash >> (band * 16)) & 0xFFFF), []):
                        if (simhash ^ other_hash).bit_count() <= 3 and _jaccard(shingles, other_shingles) >= 0.90:
                            near = True
                            break
                    if near:
                        break
                if near:
                    report["excluded"]["cross_split_near_duplicate"] += 1
                    continue
                for band in range(4):
                    near_index.setdefault((band, (simhash >> (band * 16)) & 0xFFFF), []).append((simhash, shingles))
            seen[digest] = (split, labels(row))
            output[split].append(row)

    # Restore caller-friendly output order after de-duplication.
    for split in output:
        output[split].sort(key=lambda item: item["id"])
        write_jsonl(args.out / f"{split}.jsonl", output[split])
    challenge = read_jsonl(ROOT / "nlp/data/challenge/demo_challenge.jsonl")
    challenge_rows = []
    for row in challenge:
        item = canonical(row, "challenge", "demo_challenge")
        if item:
            item["slice"] = row.get("slice", "demo")
            challenge_rows.append(item)
    write_jsonl(args.out / "challenge.jsonl", challenge_rows)
    report["splits"] = {}
    for split, rows in output.items():
        aspects = Counter(annotation["aspect"] for row in rows for annotation in row["annotations"])
        sentiments = Counter(annotation["sentiment"] for row in rows for annotation in row["annotations"])
        sources = Counter(row["source"] for row in rows)
        report["splits"][split] = {"rows": len(rows), "sources": dict(sources), "aspects": dict(aspects), "sentiments": dict(sentiments)}
    report["challenge_rows"] = len(challenge_rows)
    report["excluded"] = dict(report["excluded"])
    report["deduplicated"] = dict(report["deduplicated"])
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "experimental_dataset_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("EXPERIMENTAL ONLY: this dataset contains public mappings plus demo fixtures and must not be represented as scientific human gold.")


if __name__ == "__main__":
    main()
