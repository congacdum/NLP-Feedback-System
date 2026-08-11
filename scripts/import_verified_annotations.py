from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nlp.schema import ASPECTS, SENTIMENTS


def main() -> None:
    p = argparse.ArgumentParser(description="Validate a human-filled annotation CSV and convert it to project JSONL")
    p.add_argument("csv_file", type=Path)
    p.add_argument("--out", type=Path, default=ROOT / "nlp/data/raw/custom_verified.jsonl")
    p.add_argument("--allow-adjudication", action="store_true", help="Normally rows flagged for adjudication are rejected")
    args = p.parse_args()
    rows = []
    errors = []
    with args.csv_file.open(encoding="utf-8-sig", newline="") as f:
        for line_no, row in enumerate(csv.DictReader(f), 2):
            text = str(row.get("text") or "").strip()
            if not text:
                errors.append(f"line {line_no}: empty text")
                continue
            needs = str(row.get("needs_adjudication") or "").strip().lower() in {"1", "true", "yes", "x", "có", "co"}
            if needs and not args.allow_adjudication:
                errors.append(f"line {line_no}: needs_adjudication is still set")
            annotations = []
            for aspect in ASPECTS:
                value = str(row.get(aspect) or "").strip().lower()
                if not value:
                    continue
                if value not in SENTIMENTS:
                    errors.append(f"line {line_no}: {aspect} has invalid sentiment {value!r}")
                    continue
                annotations.append({"aspect": aspect, "sentiment": value})
            rows.append({
                "id": str(row.get("id") or f"row_{line_no}"),
                "product_id": str(row.get("product_id") or ""),
                "category": str(row.get("category") or ""),
                "text": text,
                "annotations": annotations,
                "source": "project_human_verified",
                "is_scientific_gold": True,
                "annotation_guideline_version": "1.0",
                "notes": str(row.get("notes") or "").strip(),
            })
    if errors:
        print(json.dumps({"error_count": len(errors), "errors": errors[:100]}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Validated {len(rows)} human-verified rows -> {args.out}")


if __name__ == "__main__":
    main()
