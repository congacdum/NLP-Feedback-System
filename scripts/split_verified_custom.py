from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def stable_bucket(group: str) -> float:
    value = int(hashlib.sha256(group.encode("utf-8")).hexdigest()[:12], 16)
    return value / float(16**12)


def main() -> None:
    p = argparse.ArgumentParser(description="Group-split verified custom data by product_id")
    p.add_argument("input", type=Path)
    p.add_argument("--out", type=Path, default=ROOT / "nlp/data/gold/custom")
    args = p.parse_args()
    rows = read_jsonl(args.input)
    groups = defaultdict(list)
    for row in rows:
        group = str(row.get("product_id") or row.get("id"))
        groups[group].append(row)
    split_rows = {"train": [], "dev": [], "test": []}
    for group, members in groups.items():
        b = stable_bucket(group)
        split = "train" if b < 0.70 else ("dev" if b < 0.85 else "test")
        for row in members:
            row = dict(row); row["split"] = split
            split_rows[split].append(row)
    args.out.mkdir(parents=True, exist_ok=True)
    for split, members in split_rows.items():
        with (args.out / f"{split}.jsonl").open("w", encoding="utf-8") as f:
            for row in members:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({k: len(v) for k, v in split_rows.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
