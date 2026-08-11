from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlp.preprocessing.text import normalized_hash_text
from nlp.schema import ASPECTS, SENTIMENTS, normalize_annotations


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def canonical(row: dict, split: str, *, public_mapped: bool) -> dict:
    text = str(row.get("text") or "").strip()
    if not text:
        raise ValueError(f"empty text in {row.get('id')}")
    annotations = normalize_annotations(row.get("annotations", []))
    if public_mapped:
        if row.get("safe_for_auto_gold") is not True or row.get("requires_manual_review"):
            raise ValueError(f"unsafe mapped public row reached canonical(): {row.get('id')}")
        scientific_gold = True
        mapping_status = "conservative_deterministic_mapping_from_human_annotated_source"
    else:
        if row.get("is_scientific_gold") is not True:
            raise ValueError(f"custom row is not explicitly human-verified scientific gold: {row.get('id')}")
        scientific_gold = True
        mapping_status = "project_human_verified"
    return {
        "id": str(row.get("id") or ""),
        "product_id": str(row.get("product_id") or ""),
        "category": str(row.get("category") or ""),
        "text": text,
        "annotations": annotations,
        "split": split,
        "source": str(row.get("source") or "unknown"),
        "is_scientific_gold": scientific_gold,
        "mapping_status": mapping_status,
        "annotation_guideline_version": str(row.get("annotation_guideline_version") or "source_mapping_v1"),
    }


def stats(rows: list[dict]) -> dict:
    aspects = Counter()
    sentiments = Counter()
    pairs = Counter()
    no_aspect = 0
    sources = Counter()
    for row in rows:
        sources[row.get("source", "unknown")] += 1
        anns = row.get("annotations", [])
        if not anns:
            no_aspect += 1
        for ann in anns:
            aspects[ann["aspect"]] += 1
            sentiments[ann["sentiment"]] += 1
            pairs[f"{ann['aspect']}#{ann['sentiment']}"] += 1
    return {
        "rows": len(rows),
        "no_aspect_rows": no_aspect,
        "aspects": dict(aspects),
        "sentiments": dict(sentiments),
        "pairs": dict(pairs),
        "sources": dict(sources),
    }


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Build the final project gold Train/Dev/Test from conservative public mappings "
            "plus explicitly human-verified project data. Unsafe/ambiguous upstream rows are excluded."
        )
    )
    p.add_argument("--mapped", type=Path, default=ROOT / "nlp/data/mapped")
    p.add_argument("--custom", type=Path, default=ROOT / "nlp/data/gold/custom")
    p.add_argument("--out", type=Path, default=ROOT / "nlp/data/gold")
    p.add_argument("--strict-scientific", action="store_true", help="Require all six aspects in every split and positive/neutral/negative coverage")
    args = p.parse_args()

    output: dict[str, list[dict]] = {"train": [], "dev": [], "test": []}
    excluded = Counter()
    for split in output:
        for row in read_jsonl(args.mapped / f"{split}.jsonl"):
            if row.get("safe_for_auto_gold") is not True or row.get("requires_manual_review"):
                excluded[f"public_{split}_manual_or_unsafe"] += 1
                continue
            output[split].append(canonical(row, split, public_mapped=True))
        for row in read_jsonl(args.custom / f"{split}.jsonl"):
            output[split].append(canonical(row, split, public_mapped=False))

    if not any(output.values()):
        raise SystemExit("No mapped/public or custom verified data found. Build and audit data before final gold assembly.")

    # Deduplicate within a split; never silently resolve cross-split leakage.
    seen_global: dict[str, tuple[str, str]] = {}
    duplicate_same_split = Counter()
    for split in output:
        deduped = []
        seen_local: dict[str, dict] = {}
        for row in output[split]:
            norm = normalized_hash_text(row["text"])
            if not norm:
                raise SystemExit(f"Meaningless/empty normalized text in {split}: {row['id']}")
            if norm in seen_global and seen_global[norm][0] != split:
                other_split, other_id = seen_global[norm]
                raise SystemExit(f"Cross-split leakage detected: {row['id']} ({split}) duplicates {other_id} ({other_split})")
            if norm in seen_local:
                if seen_local[norm]["annotations"] != row["annotations"]:
                    raise SystemExit(f"Conflicting duplicate labels inside {split}: {seen_local[norm]['id']} vs {row['id']}")
                duplicate_same_split[split] += 1
                continue
            seen_local[norm] = row
            seen_global[norm] = (split, row["id"])
            deduped.append(row)
        output[split] = deduped

    problems: list[str] = []
    for split, rows in output.items():
        s = stats(rows)
        missing_aspects = [a for a in ASPECTS if s["aspects"].get(a, 0) == 0]
        if split == "train" and missing_aspects:
            problems.append(f"train missing project aspects: {missing_aspects}")
        if args.strict_scientific:
            if missing_aspects:
                problems.append(f"{split} missing aspects under --strict-scientific: {missing_aspects}")
            missing_core_sent = [x for x in ("positive", "neutral", "negative") if s["sentiments"].get(x, 0) == 0]
            if missing_core_sent:
                problems.append(f"{split} missing core sentiments under --strict-scientific: {missing_core_sent}")
    if problems:
        raise SystemExit("Final gold coverage gate failed:\n- " + "\n- ".join(problems))

    args.out.mkdir(parents=True, exist_ok=True)
    for split, rows in output.items():
        write_jsonl(args.out / f"{split}.jsonl", rows)

    report = {
        "status": "built",
        "scientific_gold_claim": True,
        "policy": {
            "unsafe_public_rows_excluded": True,
            "custom_requires_is_scientific_gold_true": True,
            "cross_split_duplicates": "hard fail",
            "same_split_identical_duplicates": "deduplicated only when labels agree",
            "rating_used_as_label": False,
        },
        "excluded": dict(excluded),
        "deduplicated_same_split": dict(duplicate_same_split),
        "splits": {split: stats(rows) for split, rows in output.items()},
    }
    (args.out / "gold_build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("Next mandatory gate: scripts/check_dataset.py on the three outputs before training.")


if __name__ == "__main__":
    main()
