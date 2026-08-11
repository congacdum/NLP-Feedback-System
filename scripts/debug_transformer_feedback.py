from __future__ import annotations

"""Inspect aspect scores against tuned thresholds for one feedback string.

This is a local diagnostic helper. It does not tune thresholds, read Test data,
or change model outputs.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _configure_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def _auto_java_home() -> str | None:
    current = os.environ.get("JAVA_HOME")
    if current and (Path(current) / "bin" / "java.exe").exists():
        return current
    candidates = sorted((ROOT / ".tools" / "jre21").glob("**/bin/java.exe"))
    if not candidates:
        return None
    java_home = candidates[0].parents[1]
    os.environ["JAVA_HOME"] = str(java_home)
    os.environ["PATH"] = f"{java_home / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"
    return str(java_home)


def _fmt(value: float) -> str:
    return f"{value:.4f}"


def main() -> None:
    _configure_stdout()
    parser = argparse.ArgumentParser(description="Show Transformer aspect scores, tuned thresholds, and selected labels for one feedback.")
    parser.add_argument("text", help="Feedback text to inspect.")
    parser.add_argument("--artifact", type=Path, default=ROOT / "model_artifacts" / "experimental_phobert_absa_v2_repaired")
    parser.add_argument("--vncorenlp-dir", type=Path, default=Path(r"C:\vncorenlp"))
    parser.add_argument("--device", default="cpu", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--json", action="store_true", help="Print only machine-readable JSON.")
    args = parser.parse_args()

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    java_home = _auto_java_home()

    from nlp.inference.transformer_analyzer import TransformerAnalyzer
    from nlp.schema import ASPECTS, SENTIMENTS

    analyzer = TransformerAnalyzer(
        args.artifact,
        vncorenlp_dir=args.vncorenlp_dir,
        allow_experimental=True,
        device=args.device,
    )
    preprocess = analyzer.debug_preprocess(args.text)
    result = analyzer.analyze(args.text)
    selected = {item["aspect"]: item for item in result["aspects"]}
    rows = []
    for aspect in ASPECTS:
        score = float(result["aspect_scores"][aspect])
        threshold = float(analyzer.thresholds[aspect])
        sentiment = result["sentiment_by_aspect"][aspect]
        sentiment_dist = result["sentiment_scores"][aspect]
        rows.append({
            "aspect": aspect,
            "score": score,
            "threshold": threshold,
            "margin": score - threshold,
            "selected": aspect in selected,
            "sentiment": sentiment,
            "sentiment_score": float(sentiment_dist[sentiment]),
            "sentiment_scores": {name: float(sentiment_dist[name]) for name in SENTIMENTS},
        })

    payload = {
        "text": result["text"],
        "segmented_text": preprocess["segmented_text"],
        "artifact": str(analyzer.artifact_dir),
        "java_home": java_home,
        "threshold_source": str(analyzer.artifact_dir / "thresholds.json"),
        "backend": result["backend"],
        "model_version": result["model_version"],
        "windows_used": result["windows_used"],
        "rows": rows,
        "selected_aspects": result["aspects"],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"Text: {payload['text']}")
    print(f"Segmented: {payload['segmented_text']}")
    print(f"Artifact: {payload['artifact']}")
    print(f"Thresholds: {payload['threshold_source']}")
    print("")
    print(f"{'aspect':<18} {'score':>8} {'threshold':>10} {'margin':>8} {'selected':>9} {'sentiment':>10} {'sent_score':>10}")
    print("-" * 82)
    for row in rows:
        print(
            f"{row['aspect']:<18} "
            f"{_fmt(row['score']):>8} "
            f"{_fmt(row['threshold']):>10} "
            f"{_fmt(row['margin']):>8} "
            f"{str(row['selected']):>9} "
            f"{row['sentiment']:>10} "
            f"{_fmt(row['sentiment_score']):>10}"
        )
    print("")
    print("Selected aspects:")
    print(json.dumps(result["aspects"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
