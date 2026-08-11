from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from nlp.evaluation.metrics import evaluate_records, bootstrap_pair_macro_f1, challenge_slice_metrics
from nlp.evaluation.error_analysis import collect_errors


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def evaluate_to_dir(records: list[dict], preds: list[dict], out_dir: Path, *, bootstrap: int = 500) -> dict:
    metrics = evaluate_records(records, preds)
    metrics["pair_macro_f1_bootstrap"] = bootstrap_pair_macro_f1(records, preds, n_boot=bootstrap)
    write_json(out_dir / "metrics.json", metrics)
    write_json(out_dir / "errors.json", collect_errors(records, preds))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gold", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    gold = read_jsonl(args.gold)
    preds = read_jsonl(args.predictions)
    metrics = evaluate_to_dir(gold, preds, args.out_dir)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
