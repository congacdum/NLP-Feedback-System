from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlp.evaluation.error_analysis import collect_errors
from nlp.evaluation.metrics import bootstrap_pair_macro_f1, evaluate_records
from nlp.evaluation.plots import (
    plot_aspect_f1,
    plot_aspect_sentiment_f1,
    plot_aspect_sentiment_heatmap,
    plot_dataset_distribution,
    plot_review_length,
    plot_sentiment_confusion,
    plot_sentiment_f1,
)
from nlp.inference.transformer_analyzer import TransformerAnalyzer


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def error_summary(errors: list[dict]) -> dict:
    missing = Counter(label for error in errors for label in error["missing"])
    extra = Counter(label for error in errors for label in error["extra"])
    return {
        "error_records": len(errors),
        "top_missing_pairs": [{"label": label, "count": count} for label, count in missing.most_common(8)],
        "top_extra_pairs": [{"label": label, "count": count} for label, count in extra.most_common(8)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a frozen Transformer on a balanced ABSA diagnostic set.")
    parser.add_argument("artifact", type=Path, help="Frozen Transformer artifact")
    parser.add_argument("--test", type=Path, required=True, help="Balanced JSONL dataset")
    parser.add_argument("--vncorenlp-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None, help="Defaults to <artifact>/evaluation_balanced_v2")
    parser.add_argument("--device", default=None, help="Torch device, for example cuda or cpu")
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--allow-experimental", action="store_true")
    args = parser.parse_args()

    artifact = args.artifact.resolve()
    test_path = args.test.resolve()
    output = (args.output or artifact / "evaluation_balanced_v2").resolve()
    rows = read_jsonl(test_path)
    manifest = read_json(artifact / "training_manifest.json")
    analyzer = TransformerAnalyzer(
        artifact,
        vncorenlp_dir=args.vncorenlp_dir,
        allow_experimental=args.allow_experimental,
        device=args.device,
    )
    predictions = []
    for index, row in enumerate(rows, 1):
        predictions.append(analyzer.analyze(str(row["text"])))
        if index % 100 == 0 or index == len(rows):
            print(json.dumps({"progress": f"{index}/{len(rows)}"}, ensure_ascii=False), flush=True)

    test_metrics = evaluate_records(rows, predictions)
    errors = collect_errors(rows, predictions)
    test_metrics["pair_macro_f1_bootstrap_95"] = bootstrap_pair_macro_f1(rows, predictions, n_boot=args.bootstrap)
    test_metrics["error_analysis"] = error_summary(errors)
    metrics = {
        "artifact_kind": "transformer_absa",
        "evaluation_kind": "balanced_diagnostic",
        "scientific_final": False,
        "warning": "Balanced Diagnostic V2: candidate LLM-generated labels are structurally validated but not human-verified gold. Use this evaluation to compare aspect robustness, not as the sole deployment claim.",
        "model_version": artifact.name,
        "backbone": manifest.get("backbone_name"),
        "seed": manifest.get("seed"),
        "best_epoch": manifest.get("best_epoch"),
        "primary_metric": "pair_macro_f1_strict_union",
        "test_samples": len(rows),
        "test": test_metrics,
        "thresholds": read_json(artifact / "thresholds.json"),
        "protocol": {
            "dataset_kind": "balanced_diagnostic_candidate",
            "dataset_file": str(test_path),
            "dataset_sha256": __import__("hashlib").sha256(test_path.read_bytes()).hexdigest(),
            "thresholds_frozen_from": "development split",
            "test_used_for_model_selection": False,
            "model_retrained": False,
            "manual_verified": False,
            "is_scientific_gold": False,
        },
    }
    write_json(output / "metrics.json", metrics)
    write_json(output / "errors.json", errors)
    write_jsonl(output / "test_predictions.jsonl", predictions)
    plots = output / "plots"
    plot_dataset_distribution(rows, plots / "dataset_distribution.png", title="Phân bố khía cạnh trên Balanced Test")
    plot_aspect_sentiment_heatmap(rows, plots / "aspect_sentiment_heatmap.png")
    plot_review_length(rows, plots / "review_length_distribution.png")
    plot_aspect_f1(test_metrics, plots / "aspect_f1.png")
    plot_sentiment_f1(test_metrics, plots / "sentiment_f1.png")
    plot_aspect_sentiment_f1(test_metrics, plots / "aspect_sentiment_f1.png")
    plot_sentiment_confusion(test_metrics, plots / "sentiment_confusion.png")
    write_json(output / "evaluation_manifest.json", {
        "artifact": artifact.name,
        "evaluation_kind": "balanced_diagnostic",
        "test": str(test_path),
        "test_used_for_model_selection": False,
        "manual_verified": False,
        "is_scientific_gold": False,
        "note": "This output is separate from the natural held-out evaluation and does not replace it.",
    })
    print(json.dumps({
        "output": str(output),
        "pair_macro_f1_strict_union": test_metrics["pair_macro_f1_strict_union"],
        "aspect_macro_f1": test_metrics["aspect_macro_f1"],
        "sentiment_macro_f1": test_metrics["sentiment_macro_f1"],
        "exact_match": test_metrics["exact_match"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
