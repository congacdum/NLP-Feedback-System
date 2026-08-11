from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sklearn.metrics import cohen_kappa_score

from nlp.schema import ASPECTS, SENTIMENTS


def load(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {str(r.get("id")): r for r in csv.DictReader(f) if r.get("id")}


def value(row: dict, aspect: str) -> str:
    v = str(row.get(aspect) or "").strip().lower()
    return v if v in SENTIMENTS else "absent"


def safe_kappa(a, b, *, labels):
    score = float(cohen_kappa_score(a, b, labels=labels))
    return score if math.isfinite(score) else None


def main() -> None:
    p = argparse.ArgumentParser(description="Cohen-kappa agreement for two independent project annotation CSVs")
    p.add_argument("annotator_a", type=Path)
    p.add_argument("annotator_b", type=Path)
    args = p.parse_args()
    a, b = load(args.annotator_a), load(args.annotator_b)
    ids = sorted(set(a) & set(b))
    if not ids:
        raise SystemExit("No shared annotation ids")
    report = {"n_shared": len(ids), "per_aspect": {}}
    aspect_presence_a, aspect_presence_b = [], []
    sentiment_a, sentiment_b = [], []
    for aspect in ASPECTS:
        va = [value(a[i], aspect) for i in ids]
        vb = [value(b[i], aspect) for i in ids]
        pa = [x != "absent" for x in va]
        pb = [x != "absent" for x in vb]
        present_both = [j for j in range(len(ids)) if pa[j] and pb[j]]
        sentiment_kappa = None
        if len(present_both) >= 2:
            sentiment_kappa = safe_kappa([va[j] for j in present_both], [vb[j] for j in present_both], labels=list(SENTIMENTS))
        presence_kappa = safe_kappa(pa, pb, labels=[False, True])
        report["per_aspect"][aspect] = {
            "presence_kappa": presence_kappa,
            "sentiment_kappa_when_both_present": sentiment_kappa,
            "both_present_n": len(present_both),
        }
        aspect_presence_a.extend(pa); aspect_presence_b.extend(pb)
        for j in present_both:
            sentiment_a.append(va[j]); sentiment_b.append(vb[j])
    report["overall_presence_kappa"] = safe_kappa(aspect_presence_a, aspect_presence_b, labels=[False, True])
    report["overall_sentiment_kappa_when_both_present"] = safe_kappa(sentiment_a, sentiment_b, labels=list(SENTIMENTS)) if sentiment_a else None
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
