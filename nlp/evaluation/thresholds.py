from __future__ import annotations

from typing import Dict, Mapping, Sequence

import numpy as np
from sklearn.metrics import f1_score

from nlp.schema import ASPECTS


def tune_aspect_thresholds(records: Sequence[Mapping], predictions: Sequence[Mapping], *, grid=None) -> tuple[Dict[str, float], Dict[str, list[dict]]]:
    """Tune one threshold per aspect strictly on a development set."""
    if grid is None:
        grid = np.arange(0.20, 0.81, 0.02)
    thresholds: Dict[str, float] = {}
    curves: Dict[str, list[dict]] = {}
    for aspect in ASPECTS:
        y_true = np.array([int(any(a["aspect"] == aspect for a in r.get("annotations", []))) for r in records])
        scores = np.array([float(p.get("aspect_scores", {}).get(aspect, 0.0)) for p in predictions])
        best_t, best_f = 0.5, -1.0
        points = []
        for t in grid:
            pred = (scores >= float(t)).astype(int)
            score = float(f1_score(y_true, pred, zero_division=0))
            points.append({"threshold": round(float(t), 4), "f1": score})
            if score > best_f + 1e-12:
                best_t, best_f = float(t), score
        thresholds[aspect] = round(best_t, 4)
        curves[aspect] = points
    return thresholds, curves
