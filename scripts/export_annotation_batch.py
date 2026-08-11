from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RARE_CUES = re.compile(
    r"tư vấn|rep|trả lời|hỗ trợ|đổi trả|hoàn tiền|bảo hành|khiếu nại|nhân viên|"
    r"tặng|quà|phụ kiện|không dấu|ship|giao|đóng gói|hộp|giá|đắt|rẻ|nhưng|tuy nhiên",
    re.I,
)


def main() -> None:
    p = argparse.ArgumentParser(description="Export a deterministic human-annotation CSV from raw Lazada review candidates")
    p.add_argument("--input", type=Path, default=ROOT / "nlp/data/raw/lazada_review_candidates.jsonl")
    p.add_argument("--out", type=Path, default=ROOT / "nlp/data/raw/annotation_batch.csv")
    p.add_argument("--n", type=int, default=500)
    p.add_argument("--seed", type=int, default=20260809)
    args = p.parse_args()
    if not args.input.exists():
        raise SystemExit(f"Missing candidate file: {args.input}. Run prepare_lazada_products.py first.")
    rows = [json.loads(x) for x in args.input.read_text(encoding="utf-8").splitlines() if x.strip()]
    # Prioritize linguistically useful/rare-domain candidates, then deterministic random fill.
    scored = []
    for i, row in enumerate(rows):
        text = str(row.get("text") or "")
        score = len(RARE_CUES.findall(text)) + int(len(text.split()) >= 12)
        scored.append((score, i, row))
    scored.sort(key=lambda x: (-x[0], x[1]))
    priority_n = min(len(scored), max(0, args.n // 2))
    selected = [x[2] for x in scored[:priority_n]]
    remaining = [x[2] for x in scored[priority_n:]]
    rng = random.Random(args.seed)
    rng.shuffle(remaining)
    selected.extend(remaining[: max(0, args.n - len(selected))])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "id", "product_id", "category", "text",
        "product_quality", "delivery", "customer_service", "packaging", "price", "other",
        "needs_adjudication", "notes",
    ]
    with args.out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for idx, row in enumerate(selected, 1):
            w.writerow({
                "id": f"custom_{idx:05d}",
                "product_id": row.get("product_id", ""),
                "category": row.get("category", ""),
                "text": row.get("text", ""),
                "product_quality": "",
                "delivery": "",
                "customer_service": "",
                "packaging": "",
                "price": "",
                "other": "",
                "needs_adjudication": "",
                "notes": "",
            })
    print(f"Exported {len(selected)} rows to {args.out}")
    print("Allowed aspect cells: positive / neutral / negative / mixed / blank. Blank on all six means no_aspect.")


if __name__ == "__main__":
    main()
