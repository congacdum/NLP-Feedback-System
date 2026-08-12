from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlp.evaluation.error_analysis import collect_errors
from nlp.evaluation.metrics import (
    bootstrap_pair_macro_f1,
    challenge_slice_metrics,
    evaluate_records,
    paired_bootstrap_delta,
)
from nlp.evaluation.plots import (
    plot_aspect_f1,
    plot_aspect_sentiment_heatmap,
    plot_challenge_slices,
    plot_dataset_distribution,
    plot_dev_metric_history,
    plot_model_comparison,
    plot_pr_curves,
    plot_review_length,
    plot_sentiment_confusion,
    plot_threshold_curves,
    plot_training_history,
)
from nlp.inference.transformer_analyzer import TransformerAnalyzer


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def predict(analyzer: TransformerAnalyzer, rows: list[dict]) -> list[dict]:
    return [analyzer.analyze(str(row["text"])) for row in rows]


def main() -> None:
    p = argparse.ArgumentParser(description="Final held-out evaluation for one FROZEN Transformer artifact")
    p.add_argument("artifact", type=Path)
    p.add_argument("--train", type=Path, default=ROOT / "nlp/data/gold/train.jsonl")
    p.add_argument("--dev", type=Path, default=ROOT / "nlp/data/gold/dev.jsonl")
    p.add_argument("--test", type=Path, default=ROOT / "nlp/data/gold/test.jsonl")
    p.add_argument("--challenge", type=Path, default=ROOT / "nlp/data/challenge/final_challenge.jsonl")
    p.add_argument("--vncorenlp-dir", type=Path, default=None)
    p.add_argument("--allow-experimental", action="store_true", help="Allow evaluation of an explicitly selected experimental artifact")
    p.add_argument("--scientific-final", action="store_true", help="Use only after human-gold/data protocol gates are satisfied")
    p.add_argument("--force", action="store_true", help="Re-evaluate an artifact that already has final_evaluation.lock")
    args = p.parse_args()

    artifact = args.artifact.resolve()
    lock = artifact / "final_evaluation.lock"
    if lock.exists() and not args.force:
        raise SystemExit("Final evaluation already exists. Refusing to repeatedly inspect Test. Use --force only for a documented bug/rebuild.")
    for required in (args.train, args.dev, args.test):
        if not required.exists():
            raise SystemExit(f"Missing dataset: {required}")
    if args.scientific_final:
        # Hard guard against accidentally promoting synthetic, mapped-but-unaudited,
        # or metadata-missing rows. Scientific final requires an explicit TRUE on
        # every held protocol row; absence of the flag is not treated as consent.
        scientific_paths = [args.train, args.dev, args.test]
        if args.challenge.exists():
            scientific_paths.append(args.challenge)
        for split_path in scientific_paths:
            rows = read_jsonl(split_path)
            bad = [str(row.get("id")) for row in rows if row.get("is_scientific_gold") is not True]
            if bad:
                raise SystemExit(
                    f"Cannot mark scientific_final: {split_path} has {len(bad)} rows not explicitly is_scientific_gold=true; examples={bad[:5]}"
                )

    train, dev, test = read_jsonl(args.train), read_jsonl(args.dev), read_jsonl(args.test)
    challenge = read_jsonl(args.challenge) if args.challenge.exists() else []
    analyzer = TransformerAnalyzer(
        artifact,
        vncorenlp_dir=args.vncorenlp_dir,
        allow_experimental=args.allow_experimental,
    )
    dev_pred, test_pred = predict(analyzer, dev), predict(analyzer, test)
    challenge_pred = predict(analyzer, challenge) if challenge else []
    dev_metrics = evaluate_records(dev, dev_pred)
    test_metrics = evaluate_records(test, test_pred)
    challenge_metrics = challenge_slice_metrics(challenge, challenge_pred) if challenge else {}
    bootstrap = bootstrap_pair_macro_f1(test, test_pred, n_boot=1000)

    eval_dir = artifact / "evaluation"
    plots = eval_dir / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((artifact / "training_manifest.json").read_text(encoding="utf-8"))
    metrics = {
        "artifact_kind": "transformer_absa",
        "scientific_final": bool(args.scientific_final),
        "warning": None if args.scientific_final else "Transformer evaluation is not marked scientific_final until human-gold and protocol gates are explicitly satisfied.",
        "primary_metric": "pair_macro_f1",
        "model_version": artifact.name,
        "backbone": manifest.get("backbone_name"),
        "seed": manifest.get("seed"),
        "train_samples": len(train),
        "dev_samples": len(dev),
        "test_samples": len(test),
        "challenge_samples": len(challenge),
        "dev": dev_metrics,
        "test": test_metrics,
        "test_pair_macro_f1_bootstrap_95": bootstrap,
        "challenge": challenge_metrics,
        "protocol": {
            "dev_used_for_checkpoint_and_threshold": True,
            "test_used_for_model_selection": False,
            "final_evaluation_lock_created": True,
        },
    }

    # Apples-to-apples classical comparison. The bundled demo artifacts are NOT
    # reused here because they were trained on synthetic fixtures. Classical
    # models are fitted on the SAME final Train, thresholds are tuned on the SAME
    # Dev, and only then are all frozen candidates evaluated on the held-out Test.
    comparison = {"Transformer": test_metrics}
    challenge_comparison = {"Transformer": challenge_metrics} if challenge else {}
    try:
        from nlp.baselines.rule_absa import RuleABSA
        from nlp.baselines.tfidf_absa import LinearSVMABSA, TfidfABSA
        from nlp.evaluation.thresholds import tune_aspect_thresholds

        train_texts = [r["text"] for r in train]
        dev_texts = [r["text"] for r in dev]
        test_texts = [r["text"] for r in test]

        baseline = TfidfABSA(model_version="tfidf-lr-final-comparison").fit(train)
        baseline_dev_raw = baseline.predict_full(dev_texts)
        baseline_thresholds, _ = tune_aspect_thresholds(dev, baseline_dev_raw)
        baseline.set_thresholds(baseline_thresholds)

        svm = LinearSVMABSA(model_version="linear-svm-final-comparison").fit(train)
        svm_dev_raw = svm.predict_full(dev_texts)
        svm_thresholds, _ = tune_aspect_thresholds(dev, svm_dev_raw)
        svm.set_thresholds(svm_thresholds)

        rule = RuleABSA()
        b_pred = baseline.predict_full(test_texts)
        s_pred = svm.predict_full(test_texts)
        r_pred = [rule.analyze(text) for text in test_texts]
        b_metrics = evaluate_records(test, b_pred)
        s_metrics = evaluate_records(test, s_pred)
        r_metrics = evaluate_records(test, r_pred)
        comparison = {"Rule": r_metrics, "LinearSVM": s_metrics, "TF-IDF LR": b_metrics, "Transformer": test_metrics}
        metrics["comparison_same_test"] = comparison
        metrics["classical_comparison_protocol"] = {
            "fit_split": "train",
            "threshold_split": "dev",
            "evaluation_split": "test",
            "bundled_demo_artifacts_reused": False,
            "tfidf_thresholds": baseline_thresholds,
            "svm_thresholds": svm_thresholds,
        }
        metrics["paired_bootstrap_tfidf_to_transformer"] = paired_bootstrap_delta(test, b_pred, test_pred, n_boot=1000)
        metrics["paired_bootstrap_svm_to_transformer"] = paired_bootstrap_delta(test, s_pred, test_pred, n_boot=1000)
        if challenge:
            challenge_texts = [r["text"] for r in challenge]
            b_ch = baseline.predict_full(challenge_texts)
            s_ch = svm.predict_full(challenge_texts)
            r_ch = [rule.analyze(text) for text in challenge_texts]
            challenge_comparison = {
                "Rule": challenge_slice_metrics(challenge, r_ch),
                "LinearSVM": challenge_slice_metrics(challenge, s_ch),
                "TF-IDF LR": challenge_slice_metrics(challenge, b_ch),
                "Transformer": challenge_metrics,
            }
    except Exception as exc:
        metrics["comparison_note"] = f"Classical comparison unavailable: {type(exc).__name__}: {exc}"

    write_json(eval_dir / "metrics.json", metrics)
    write_json(eval_dir / "errors.json", collect_errors(test, test_pred))
    write_json(eval_dir / "challenge_errors.json", collect_errors(challenge, challenge_pred) if challenge else [])
    write_jsonl(eval_dir / "test_predictions.jsonl", test_pred)
    if challenge:
        write_jsonl(eval_dir / "challenge_predictions.jsonl", challenge_pred)

    plot_dataset_distribution(train, plots / "dataset_distribution.png")
    plot_aspect_sentiment_heatmap(train, plots / "aspect_sentiment_heatmap.png")
    plot_review_length(train, plots / "review_length_distribution.png")
    plot_aspect_f1(test_metrics, plots / "aspect_f1.png")
    plot_sentiment_confusion(test_metrics, plots / "sentiment_confusion.png")
    plot_pr_curves(dev, dev_pred, plots / "pr_curves_dev.png")
    plot_model_comparison(comparison, plots / "model_comparison.png")
    if challenge_comparison:
        plot_challenge_slices(challenge_comparison, plots / "challenge_performance.png")
    history = manifest.get("history") or []
    plot_training_history(history, plots / "train_dev_loss.png")
    plot_dev_metric_history(history, plots / "dev_pair_f1.png")
    curves_path = artifact / "dev_threshold_curves.json"
    if curves_path.exists():
        plot_threshold_curves(json.loads(curves_path.read_text(encoding="utf-8")), plots / "threshold_f1.png")

    write_json(eval_dir / "evaluation_manifest.json", {
        "artifact": artifact.name,
        "scientific_final": bool(args.scientific_final),
        "train": str(args.train),
        "dev": str(args.dev),
        "test": str(args.test),
        "challenge": str(args.challenge) if challenge else None,
        "test_used_for_model_selection": False,
        "note": "If code/data bugs are discovered after this point, document them and create a new model/evaluation version rather than silently tuning on this Test.",
    })
    lock.write_text(json.dumps({"artifact": artifact.name, "scientific_final": bool(args.scientific_final)}, indent=2), encoding="utf-8")
    print(json.dumps({"artifact": artifact.name, "test_pair_macro_f1": test_metrics["pair_macro_f1"], "scientific_final": bool(args.scientific_final)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
