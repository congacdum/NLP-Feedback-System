from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from nlp.evaluation.plots import (
    plot_aspect_f1,
    plot_dev_metric_history,
    plot_sentiment_confusion,
    plot_threshold_curves,
    plot_training_history,
)
from nlp.schema import ASPECTS, ASPECT_VI, SENTIMENTS, SENTIMENT_VI


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def save_plot(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_aspect_support(metrics: dict, path: Path) -> None:
    values = [metrics.get("per_aspect", {}).get(aspect, {}).get("support", 0) for aspect in ASPECTS]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar([ASPECT_VI[aspect] for aspect in ASPECTS], values, color="#4f46e5")
    ax.set_ylabel("Số nhãn gold trong Dev")
    ax.set_title("Support theo khía cạnh")
    ax.tick_params(axis="x", rotation=25)
    ax.bar_label(bars, padding=3, fontsize=8)
    save_plot(fig, path)


def plot_aspect_sentiment_f1(metrics: dict, path: Path) -> None:
    pair_metrics = metrics.get("per_pair", {})
    matrix = np.zeros((len(ASPECTS), len(SENTIMENTS)), dtype=float)
    support = np.zeros((len(ASPECTS), len(SENTIMENTS)), dtype=int)
    for row, aspect in enumerate(ASPECTS):
        for col, sentiment in enumerate(SENTIMENTS):
            item = pair_metrics.get(f"{aspect}#{sentiment}", {})
            matrix[row, col] = float(item.get("f1", 0.0))
            support[row, col] = int(item.get("support", 0))

    fig, ax = plt.subplots(figsize=(8, 5.2))
    image = ax.imshow(matrix, vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
    ax.set_xticks(range(len(SENTIMENTS)), [SENTIMENT_VI[value] for value in SENTIMENTS])
    ax.set_yticks(range(len(ASPECTS)), [ASPECT_VI[value] for value in ASPECTS])
    ax.set_title("F1 của từng cặp khía cạnh × sentiment trên Dev")
    for row in range(len(ASPECTS)):
        for col in range(len(SENTIMENTS)):
            label = "-" if support[row, col] == 0 else f"{matrix[row, col]:.2f}"
            ax.text(col, row, label, ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.035, label="F1")
    save_plot(fig, path)


def plot_sentiment_f1(metrics: dict, path: Path) -> None:
    values = [metrics.get("per_sentiment", {}).get(sentiment, {}).get("f1", 0.0) for sentiment in SENTIMENTS]
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    bars = ax.bar([SENTIMENT_VI[value] for value in SENTIMENTS], values, color=["#059669", "#64748b", "#e11d48", "#d97706"])
    ax.set_ylim(0, 1.03)
    ax.set_ylabel("F1")
    ax.set_title("F1 theo sentiment trên Dev")
    ax.bar_label(bars, labels=[f"{value:.3f}" for value in values], padding=3, fontsize=8)
    save_plot(fig, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build read-only Dev evaluation files from a frozen Transformer artifact")
    parser.add_argument("artifact", type=Path, help="Transformer artifact containing dev_metrics.json")
    parser.add_argument("--output", type=Path, default=None, help="Defaults to <artifact>/evaluation_dev")
    args = parser.parse_args()

    artifact = args.artifact.resolve()
    required = [artifact / "dev_metrics.json", artifact / "training_manifest.json", artifact / "thresholds.json"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"Missing required artifact files: {missing}")

    output = (args.output or artifact / "evaluation_dev").resolve()
    plots = output / "plots"
    dev_metrics = read_json(artifact / "dev_metrics.json")
    manifest = read_json(artifact / "training_manifest.json")
    thresholds = read_json(artifact / "thresholds.json")
    training_config_path = artifact / "training_config.json"
    training_config = read_json(training_config_path) if training_config_path.exists() else {}

    plot_training_history(manifest.get("history", []), plots / "train_dev_loss.png")
    plot_dev_metric_history(manifest.get("history", []), plots / "dev_pair_f1.png", metric_key="dev_pair_macro_f1_strict_union")
    plot_aspect_f1(dev_metrics, plots / "aspect_f1.png")
    plot_sentiment_f1(dev_metrics, plots / "sentiment_f1.png")
    plot_aspect_support(dev_metrics, plots / "aspect_support.png")
    plot_aspect_sentiment_f1(dev_metrics, plots / "aspect_sentiment_f1.png")
    plot_sentiment_confusion(dev_metrics, plots / "sentiment_confusion.png")
    curves_path = artifact / "dev_threshold_curves.json"
    if curves_path.exists():
        plot_threshold_curves(read_json(curves_path), plots / "threshold_f1.png")

    evaluation = {
        "artifact_kind": "transformer_absa",
        "evaluation_kind": "dev_validation",
        "scientific_final": False,
        "warning": "Development validation only. The same Dev split selected the checkpoint and tuned thresholds; these values are not held-out Test results.",
        "model_version": artifact.name,
        "backbone": manifest.get("backbone_name"),
        "seed": manifest.get("seed"),
        "best_epoch": manifest.get("best_epoch"),
        "primary_metric": manifest.get("primary_metric"),
        "dev": dev_metrics,
        "thresholds": thresholds,
        "training": {
            key: training_config.get(key)
            for key in ("epochs", "batch_size", "max_length", "learning_rate", "weight_decay", "warmup_ratio", "patience", "device", "weighting_strategy")
            if key in training_config
        },
        "protocol": {
            "checkpoint_selected_on": "dev",
            "thresholds_tuned_on": "dev",
            "held_out_test_read": bool(manifest.get("test_was_used", False)),
            "inference_run_while_viewing_dashboard": False,
        },
    }
    write_json(output / "metrics.json", evaluation)
    write_json(output / "evaluation_manifest.json", {
        "artifact": artifact.name,
        "evaluation_kind": "dev_validation",
        "source_files": [path.name for path in required] + (["dev_threshold_curves.json"] if curves_path.exists() else []),
        "note": "Generated from saved training artifacts only; no model inference and no held-out Test access occurred.",
    })
    print(json.dumps({"output": str(output), "plots": len(list(plots.glob("*.png"))), "dev_pair_macro_f1": dev_metrics.get("pair_macro_f1_strict_union")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
