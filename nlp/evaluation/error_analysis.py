from __future__ import annotations

from typing import Mapping, Sequence

from nlp.schema import pair_labels


def collect_errors(gold: Sequence[Mapping], preds: Sequence[Mapping]) -> list[dict]:
    errors = []
    for row, pred in zip(gold, preds):
        g = pair_labels(row.get("annotations", []))
        p = {f"{a['aspect']}#{a['sentiment']}" for a in pred.get("aspects", [])}
        if g != p:
            errors.append({
                "id": row.get("id"),
                "text": row.get("text"),
                "gold_pairs": sorted(g),
                "pred_pairs": sorted(p),
                "missing": sorted(g - p),
                "extra": sorted(p - g),
                "aspect_scores": pred.get("aspect_scores", {}),
                "backend": pred.get("backend"),
            })
    return errors
