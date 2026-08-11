from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Mapping, Sequence

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix,
)
from sklearn.preprocessing import MultiLabelBinarizer

from nlp.schema import ASPECTS, SENTIMENTS, pair_labels

PAIR_CLASSES = [f"{a}#{s}" for a in ASPECTS for s in SENTIMENTS]


def _gold_pairs(record: Mapping) -> set[str]:
    return pair_labels(record.get("annotations", []))


def _pred_pairs(pred: Mapping) -> set[str]:
    return {f"{a['aspect']}#{a['sentiment']}" for a in pred.get("aspects", [])}


def _gold_aspects(record: Mapping) -> set[str]:
    return {a["aspect"] for a in record.get("annotations", [])}


def _pred_aspects(pred: Mapping) -> set[str]:
    return {a["aspect"] for a in pred.get("aspects", [])}


def compute_pair_metrics(gold: Sequence[Mapping], preds: Sequence[Mapping]) -> Dict:
    mlb = MultiLabelBinarizer(classes=PAIR_CLASSES)
    y_true = mlb.fit_transform([_gold_pairs(x) for x in gold])
    y_pred = mlb.transform([_pred_pairs(x) for x in preds])
    per_class = precision_recall_fscore_support(y_true, y_pred, average=None, zero_division=0)
    support = y_true.sum(axis=0)
    # Primary Pair Macro-F1 uses the pair classes PRESENT IN GOLD. This keeps
    # the denominator fixed across candidate models on the same Dev/Test set.
    # A second strict-union diagnostic includes hallucinated pair classes that
    # are absent from gold, while Micro-F1 and Exact Match also penalize them.
    gold_active = np.where(y_true.sum(axis=0) > 0)[0]
    union_active = np.where((y_true.sum(axis=0) + y_pred.sum(axis=0)) > 0)[0]
    if len(gold_active):
        pair_macro = float(f1_score(y_true[:, gold_active], y_pred[:, gold_active], average="macro", zero_division=0))
        pair_micro = float(f1_score(y_true, y_pred, average="micro", zero_division=0))
    else:
        # Pair-F1 is mathematically undefined for an all-no_aspect gold slice.
        # Use exact set agreement so correct abstention is represented honestly.
        pair_macro = float(accuracy_score(y_true, y_pred))
        pair_micro = pair_macro if not len(union_active) else float(f1_score(y_true, y_pred, average="micro", zero_division=0))
    pair_macro_union = (
        float(f1_score(y_true[:, union_active], y_pred[:, union_active], average="macro", zero_division=0))
        if len(union_active) else float(accuracy_score(y_true, y_pred))
    )
    unseen_cols = np.where((y_true.sum(axis=0) == 0) & (y_pred.sum(axis=0) > 0))[0]
    unseen_fp = int(y_pred[:, unseen_cols].sum()) if len(unseen_cols) else 0
    return {
        "pair_macro_f1": pair_macro,
        "pair_macro_f1_strict_union": pair_macro_union,
        "pair_micro_f1": pair_micro,
        "pair_unseen_gold_false_positives": unseen_fp,
        "exact_match": float(accuracy_score(y_true, y_pred)),
        "per_pair": {
            cls: {
                "precision": float(per_class[0][i]),
                "recall": float(per_class[1][i]),
                "f1": float(per_class[2][i]),
                "support": int(support[i]),
            }
            for i, cls in enumerate(PAIR_CLASSES)
        },
    }


def compute_aspect_metrics(gold: Sequence[Mapping], preds: Sequence[Mapping]) -> Dict:
    mlb = MultiLabelBinarizer(classes=list(ASPECTS))
    y_true = mlb.fit_transform([_gold_aspects(x) for x in gold])
    y_pred = mlb.transform([_pred_aspects(x) for x in preds])
    p, r, f, support = precision_recall_fscore_support(y_true, y_pred, average=None, zero_division=0)
    return {
        "aspect_macro_precision": float(precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)[0]),
        "aspect_macro_recall": float(precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)[1]),
        "aspect_macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "aspect_micro_f1": float(f1_score(y_true, y_pred, average="micro", zero_division=0)),
        "per_aspect": {
            aspect: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(support[i])}
            for i, aspect in enumerate(ASPECTS)
        },
    }


def compute_conditional_sentiment_metrics(gold: Sequence[Mapping], preds: Sequence[Mapping]) -> Dict:
    """Sentiment quality conditional on a gold aspect being present.

    End-to-end misses are penalized by Pair F1; this metric isolates polarity quality.
    If a predictor exposes `sentiment_by_aspect`, it is used even when the aspect
    threshold did not fire. Otherwise a missing predicted aspect becomes `neutral`
    only for the purpose of this conditional diagnostic metric.
    """
    y_true: List[str] = []
    y_pred: List[str] = []
    by_aspect: Dict[str, Dict[str, List[str]]] = {a: {"gold": [], "pred": []} for a in ASPECTS}
    for g, p in zip(gold, preds):
        pred_map = dict(p.get("sentiment_by_aspect", {}))
        pred_map.update({a["aspect"]: a["sentiment"] for a in p.get("aspects", [])})
        for ann in g.get("annotations", []):
            aspect, sent = ann["aspect"], ann["sentiment"]
            pred_sent = pred_map.get(aspect, "neutral")
            y_true.append(sent); y_pred.append(pred_sent)
            by_aspect[aspect]["gold"].append(sent); by_aspect[aspect]["pred"].append(pred_sent)
    if not y_true:
        return {"sentiment_macro_f1": 0.0, "per_sentiment": {}, "per_aspect_sentiment_f1": {}}
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=list(SENTIMENTS), average=None, zero_division=0)
    per_aspect = {}
    for aspect, vals in by_aspect.items():
        per_aspect[aspect] = float(f1_score(vals["gold"], vals["pred"], labels=list(SENTIMENTS), average="macro", zero_division=0)) if vals["gold"] else 0.0
    return {
        "sentiment_macro_f1": float(f1_score(y_true, y_pred, labels=list(SENTIMENTS), average="macro", zero_division=0)),
        "per_sentiment": {
            sent: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
            for i, sent in enumerate(SENTIMENTS)
        },
        "per_aspect_sentiment_f1": per_aspect,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=list(SENTIMENTS)).tolist(),
    }


def evaluate_records(gold: Sequence[Mapping], preds: Sequence[Mapping]) -> Dict:
    if len(gold) != len(preds):
        raise ValueError("gold and preds must have the same length")
    result = {}
    result.update(compute_pair_metrics(gold, preds))
    result.update(compute_aspect_metrics(gold, preds))
    result.update(compute_conditional_sentiment_metrics(gold, preds))
    result["n_samples"] = len(gold)
    return result


def bootstrap_pair_macro_f1(gold: Sequence[Mapping], preds: Sequence[Mapping], *, n_boot: int = 500, seed: int = 42) -> Dict[str, float]:
    if not gold:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    rng = np.random.default_rng(seed)
    scores = []
    n = len(gold)
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        g = [gold[i] for i in idx]
        p = [preds[i] for i in idx]
        scores.append(compute_pair_metrics(g, p)["pair_macro_f1"])
    return {
        "mean": float(np.mean(scores)),
        "ci_low": float(np.percentile(scores, 2.5)),
        "ci_high": float(np.percentile(scores, 97.5)),
    }


def paired_bootstrap_delta(gold: Sequence[Mapping], preds_a: Sequence[Mapping], preds_b: Sequence[Mapping], *, n_boot: int = 500, seed: int = 42) -> Dict[str, float]:
    if len(gold) != len(preds_a) or len(gold) != len(preds_b):
        raise ValueError("all collections must have same length")
    rng = np.random.default_rng(seed)
    n = len(gold)
    deltas = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        g = [gold[i] for i in idx]
        a = [preds_a[i] for i in idx]
        b = [preds_b[i] for i in idx]
        deltas.append(compute_pair_metrics(g, b)["pair_macro_f1"] - compute_pair_metrics(g, a)["pair_macro_f1"])
    return {
        "mean_delta": float(np.mean(deltas)),
        "ci_low": float(np.percentile(deltas, 2.5)),
        "ci_high": float(np.percentile(deltas, 97.5)),
        "prob_b_better": float(np.mean(np.array(deltas) > 0)),
    }


def challenge_slice_metrics(records: Sequence[Mapping], preds: Sequence[Mapping]) -> Dict[str, Dict[str, float]]:
    groups: Dict[str, List[int]] = defaultdict(list)
    for i, row in enumerate(records):
        groups[str(row.get("slice", "unknown"))].append(i)
    out = {}
    for name, indices in groups.items():
        g = [records[i] for i in indices]
        p = [preds[i] for i in indices]
        metrics = compute_pair_metrics(g, p)
        out[name] = {
            "pair_macro_f1": metrics["pair_macro_f1"],
            "pair_micro_f1": metrics["pair_micro_f1"],
            "exact_match": metrics["exact_match"],
            "n": len(indices),
        }
    return out
