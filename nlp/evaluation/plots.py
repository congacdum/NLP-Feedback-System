from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import precision_recall_curve

from nlp.schema import ASPECTS, SENTIMENTS, ASPECT_VI, SENTIMENT_VI


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_dataset_distribution(records: Sequence[Mapping], path: Path) -> None:
    counts = Counter(a["aspect"] for r in records for a in r.get("annotations", []))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar([ASPECT_VI[a] for a in ASPECTS], [counts[a] for a in ASPECTS])
    ax.set_ylabel("Số lượt gán nhãn")
    ax.set_title("Phân bố khía cạnh")
    ax.tick_params(axis="x", rotation=25)
    _save(fig, path)


def plot_aspect_sentiment_heatmap(records: Sequence[Mapping], path: Path) -> None:
    matrix = np.zeros((len(ASPECTS), len(SENTIMENTS)), dtype=int)
    for r in records:
        for ann in r.get("annotations", []):
            matrix[ASPECTS.index(ann["aspect"]), SENTIMENTS.index(ann["sentiment"])] += 1
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(matrix, aspect="auto")
    ax.set_xticks(range(len(SENTIMENTS)), [SENTIMENT_VI[s] for s in SENTIMENTS])
    ax.set_yticks(range(len(ASPECTS)), [ASPECT_VI[a] for a in ASPECTS])
    for i in range(len(ASPECTS)):
        for j in range(len(SENTIMENTS)):
            ax.text(j, i, str(matrix[i, j]), ha="center", va="center")
    ax.set_title("Khía cạnh × cảm xúc")
    fig.colorbar(im, ax=ax, fraction=0.03)
    _save(fig, path)


def plot_review_length(records: Sequence[Mapping], path: Path) -> None:
    lengths = [len(str(r.get("text", "")).split()) for r in records]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(lengths, bins=min(25, max(5, len(set(lengths)))))
    ax.set_xlabel("Số token theo khoảng trắng")
    ax.set_ylabel("Số feedback")
    ax.set_title("Phân bố độ dài feedback")
    _save(fig, path)


def plot_aspect_f1(metrics: Mapping, path: Path) -> None:
    values = [metrics["per_aspect"][a]["f1"] for a in ASPECTS]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar([ASPECT_VI[a] for a in ASPECTS], values)
    ax.set_ylim(0, 1)
    ax.set_ylabel("F1")
    ax.set_title("F1 theo khía cạnh")
    ax.tick_params(axis="x", rotation=25)
    _save(fig, path)


def plot_sentiment_confusion(metrics: Mapping, path: Path) -> None:
    matrix = np.array(metrics.get("confusion_matrix", np.zeros((4,4))))
    fig, ax = plt.subplots(figsize=(5.5, 5))
    im = ax.imshow(matrix)
    labels = [SENTIMENT_VI[s] for s in SENTIMENTS]
    ax.set_xticks(range(4), labels, rotation=30)
    ax.set_yticks(range(4), labels)
    ax.set_xlabel("Dự đoán")
    ax.set_ylabel("Nhãn thật")
    ax.set_title("Ma trận nhầm lẫn sentiment (conditional)")
    for i in range(4):
        for j in range(4):
            ax.text(j, i, str(int(matrix[i, j])), ha="center", va="center")
    fig.colorbar(im, ax=ax, fraction=0.04)
    _save(fig, path)


def plot_threshold_curves(curves: Mapping[str, Sequence[Mapping]], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for aspect in ASPECTS:
        pts = curves.get(aspect, [])
        if pts:
            ax.plot([p["threshold"] for p in pts], [p["f1"] for p in pts], label=ASPECT_VI[aspect])
    ax.set_xlabel("Threshold")
    ax.set_ylabel("F1 trên Dev")
    ax.set_ylim(0, 1.03)
    ax.set_title("Tối ưu threshold theo khía cạnh (Dev only)")
    ax.legend(fontsize=8)
    _save(fig, path)


def plot_pr_curves(records: Sequence[Mapping], preds: Sequence[Mapping], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    for aspect in ASPECTS:
        y = np.array([int(any(a["aspect"] == aspect for a in r.get("annotations", []))) for r in records])
        scores = np.array([float(p.get("aspect_scores", {}).get(aspect, 0.0)) for p in preds])
        if len(np.unique(y)) < 2:
            continue
        precision, recall, _ = precision_recall_curve(y, scores)
        ax.plot(recall, precision, label=ASPECT_VI[aspect])
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision–Recall theo khía cạnh")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.03)
    ax.legend(fontsize=8)
    _save(fig, path)


def plot_model_comparison(models: Mapping[str, Mapping], path: Path) -> None:
    names = list(models.keys())
    pair = [models[n].get("pair_macro_f1", 0) for n in names]
    aspect = [models[n].get("aspect_macro_f1", 0) for n in names]
    x = np.arange(len(names)); width = 0.34
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.bar(x - width/2, pair, width, label="Pair Macro-F1")
    ax.bar(x + width/2, aspect, width, label="Aspect Macro-F1")
    ax.set_xticks(x, names)
    ax.set_ylim(0, 1)
    ax.set_title("So sánh mô hình trên cùng tập đánh giá")
    ax.legend()
    _save(fig, path)


def plot_challenge_slices(comparison: Mapping[str, Mapping[str, Mapping]], path: Path) -> None:
    model_names = list(comparison.keys())
    slices = sorted({s for m in comparison.values() for s in m.keys()})
    if not slices:
        return
    x = np.arange(len(slices)); width = 0.8 / max(1, len(model_names))
    fig, ax = plt.subplots(figsize=(max(8, len(slices)*0.85), 5))
    for mi, model in enumerate(model_names):
        vals = [comparison[model].get(s, {}).get("pair_macro_f1", 0) for s in slices]
        ax.bar(x - 0.4 + width/2 + mi*width, vals, width, label=model)
    ax.set_xticks(x, slices, rotation=35, ha="right")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Pair Macro-F1")
    ax.set_title("Semantic Challenge theo nhóm")
    ax.legend()
    _save(fig, path)


def plot_learning_curve(points: Sequence[Mapping], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.plot([p["fraction"] for p in points], [p["dev_pair_macro_f1"] for p in points], marker="o")
    ax.set_xlabel("Tỷ lệ dữ liệu Train")
    ax.set_ylabel("Dev Pair Macro-F1")
    ax.set_ylim(0, 1)
    ax.set_title("Learning curve của baseline")
    _save(fig, path)


def plot_training_history(history: Sequence[Mapping], path: Path, metric_key: str = "dev_pair_macro_f1") -> None:
    if not history:
        return
    fig, ax = plt.subplots(figsize=(7, 4.2))
    epochs = [h["epoch"] for h in history]
    if all("train_loss" in h for h in history):
        ax.plot(epochs, [h["train_loss"] for h in history], label="Train loss")
    if all("dev_loss" in h for h in history):
        ax.plot(epochs, [h["dev_loss"] for h in history], label="Dev loss")
    ax.set_xlabel("Epoch"); ax.set_title("Train / Dev learning curves")
    ax.legend()
    _save(fig, path)


def plot_dev_metric_history(history: Sequence[Mapping], path: Path, metric_key: str = "dev_pair_macro_f1") -> None:
    if not history:
        return
    points = [(h.get("epoch"), h.get(metric_key)) for h in history if h.get(metric_key) is not None]
    if not points:
        return
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot([p[0] for p in points], [p[1] for p in points], marker="o")
    ax.set_xlabel("Epoch")
    ax.set_ylabel(metric_key)
    ax.set_ylim(0, 1)
    ax.set_title("Dev Pair Macro-F1 theo epoch")
    _save(fig, path)
