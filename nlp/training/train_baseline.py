from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlp.baselines.rule_absa import RuleABSA
from nlp.baselines.tfidf_absa import LinearSVMABSA, TfidfABSA
from nlp.evaluation.error_analysis import collect_errors
from nlp.evaluation.metrics import (
    evaluate_records,
    bootstrap_pair_macro_f1,
    paired_bootstrap_delta,
    challenge_slice_metrics,
)
from nlp.evaluation.thresholds import tune_aspect_thresholds


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dump_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def predictions(model, rows: list[dict]) -> list[dict]:
    if hasattr(model, "predict_full"):
        return model.predict_full([r["text"] for r in rows])
    return [model.analyze(r["text"]) for r in rows]


def fit_fraction(rows: list[dict], fraction: float) -> list[dict]:
    # Deterministic stratification-lite: take evenly spaced rows instead of head-only.
    if fraction >= 0.999:
        return rows
    n = max(24, int(len(rows) * fraction))
    step = len(rows) / n
    indices = sorted({min(len(rows)-1, int(i * step)) for i in range(n)})
    subset = [rows[i] for i in indices]
    # Guard: every aspect needs pos/neg examples for binary aspect classifiers.
    aspects = {a["aspect"] for r in subset for a in r.get("annotations", [])}
    if len(aspects) < 6:
        return rows[:n]
    return subset


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Rule, TF-IDF Logistic Regression and LinearSVM ABSA baselines")
    parser.add_argument("--train", type=Path, default=ROOT / "nlp/data/demo/train.jsonl")
    parser.add_argument("--dev", type=Path, default=ROOT / "nlp/data/demo/dev.jsonl")
    parser.add_argument("--test", type=Path, default=ROOT / "nlp/data/demo/test.jsonl")
    parser.add_argument("--challenge", type=Path, default=ROOT / "nlp/data/challenge/demo_challenge.jsonl")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "model_artifacts/baseline_absa_v0")
    parser.add_argument("--experimental", action="store_true", help="Mark the artifact as non-scientific experimental data.")
    parser.add_argument("--bootstrap-iterations", type=int, default=300)
    parser.add_argument("--skip-learning-curve", action="store_true")
    parser.add_argument("--skip-plots", action="store_true")
    args = parser.parse_args()
    for split in (args.train, args.dev, args.test):
        if not split.exists():
            raise SystemExit(f"Dataset split not found: {split}")
    train, dev, test = read_jsonl(args.train), read_jsonl(args.dev), read_jsonl(args.test)
    challenge = read_jsonl(args.challenge) if args.challenge.exists() else []
    if not train or not dev or not test:
        raise SystemExit("Train, Dev and Test must all contain at least one row")

    out = args.output_dir
    eval_dir = out / "evaluation"
    plots = eval_dir / "plots"
    plots.mkdir(parents=True, exist_ok=True)

    model = TfidfABSA().fit(train)
    dev_raw = predictions(model, dev)
    thresholds, threshold_curves = tune_aspect_thresholds(dev, dev_raw)
    model.set_thresholds(thresholds)
    joblib.dump(model, out / "baseline.joblib")
    dump_json(out / "thresholds.json", thresholds)

    svm = LinearSVMABSA().fit(train)
    svm_dev_raw = predictions(svm, dev)
    svm_thresholds, _svm_threshold_curves = tune_aspect_thresholds(dev, svm_dev_raw)
    svm.set_thresholds(svm_thresholds)
    joblib.dump(svm, out / "linear_svm_baseline.joblib")
    dump_json(out / "linear_svm_thresholds.json", svm_thresholds)

    dev_pred = predictions(model, dev)
    svm_dev = predictions(svm, dev)
    tfidf_dev_metrics = evaluate_records(dev, dev_pred)
    svm_dev_metrics = evaluate_records(dev, svm_dev)
    # Candidate selection is deliberately Dev-only.  Test is evaluated only
    # after this frozen selection, never used to pick a baseline.
    selected_name, selected_model = ("linear_svm", svm) if svm_dev_metrics["pair_macro_f1_strict_union"] > tfidf_dev_metrics["pair_macro_f1_strict_union"] else ("tfidf_logistic_regression", model)
    selected_test = predictions(selected_model, test)
    test_pred = predictions(model, test)
    challenge_pred = predictions(model, challenge)
    svm_test = predictions(svm, test)
    svm_challenge = predictions(svm, challenge)
    rule = RuleABSA()
    rule_test = predictions(rule, test)
    rule_challenge = predictions(rule, challenge)

    dev_metrics = tfidf_dev_metrics
    test_metrics = evaluate_records(test, test_pred)
    svm_metrics = evaluate_records(test, svm_test)
    selected_test_metrics = evaluate_records(test, selected_test)
    rule_metrics = evaluate_records(test, rule_test)
    challenge_metrics = challenge_slice_metrics(challenge, challenge_pred)
    svm_challenge_metrics = challenge_slice_metrics(challenge, svm_challenge)
    rule_challenge_metrics = challenge_slice_metrics(challenge, rule_challenge)
    bootstrap = bootstrap_pair_macro_f1(test, selected_test, n_boot=args.bootstrap_iterations)
    paired = paired_bootstrap_delta(test, rule_test, selected_test, n_boot=args.bootstrap_iterations)

    learning = []
    if not args.skip_learning_curve:
        for frac in (0.25, 0.50, 0.75, 1.0):
            subset = fit_fraction(train, frac)
            m = TfidfABSA(model_version=f"baseline-learning-{frac:.2f}").fit(subset)
            raw = predictions(m, dev)
            th, _ = tune_aspect_thresholds(dev, raw)
            m.set_thresholds(th)
            score = evaluate_records(dev, predictions(m, dev))["pair_macro_f1_strict_union"]
            learning.append({"fraction": frac, "n_train": len(subset), "dev_pair_macro_f1_strict_union": score})

    metrics = {
        "artifact_kind": "experimental_baseline" if args.experimental else "demo_baseline",
        "scientific_final": False,
        "experimental_only": bool(args.experimental),
        "warning": "Metrics are non-scientific: this artifact is not trained/evaluated on human-verified gold data.",
        "primary_metric": "pair_macro_f1_strict_union",
        "model_version": model.model_version,
        "train_samples": len(train),
        "dev_samples": len(dev),
        "test_samples": len(test),
        "challenge_samples": len(challenge),
        "dev": dev_metrics,
        "linear_svm_dev": svm_dev_metrics,
        "selected_on_dev": selected_name,
        "selected_test": selected_test_metrics,
        "test": test_metrics,
        "linear_svm_test": svm_metrics,
        "rule_test": rule_metrics,
        "test_pair_macro_f1_bootstrap_95": bootstrap,
        "paired_bootstrap_rule_to_baseline": paired,
        "challenge": challenge_metrics,
        "linear_svm_challenge": svm_challenge_metrics,
        "rule_challenge": rule_challenge_metrics,
        "learning_curve": learning,
    }
    dump_json(eval_dir / "metrics.json", metrics)
    dump_json(eval_dir / "threshold_curves.json", threshold_curves)
    dump_json(eval_dir / "errors.json", collect_errors(test, test_pred))
    dump_json(eval_dir / "challenge_errors.json", collect_errors(challenge, challenge_pred))
    dump_json(eval_dir / "evaluation_manifest.json", {
        "data": "experimental_dataset" if args.experimental else "project_demo_fixture",
        "is_scientific_gold": False,
        "test_used_for_model_selection": False,
        "dev_used_for_threshold_tuning": True,
        "selection_metric": "pair_macro_f1_strict_union",
    })

    if not args.skip_plots:
        # Matplotlib is deliberately lazy-imported.  It is not part of the
        # training/evaluation contract and must not block headless training.
        from nlp.evaluation.plots import (
            plot_dataset_distribution, plot_aspect_sentiment_heatmap,
            plot_review_length, plot_aspect_f1, plot_sentiment_confusion,
            plot_threshold_curves, plot_pr_curves, plot_model_comparison,
            plot_challenge_slices, plot_learning_curve,
        )
        plot_dataset_distribution(train, plots / "dataset_distribution.png")
        plot_aspect_sentiment_heatmap(train, plots / "aspect_sentiment_heatmap.png")
        plot_review_length(train, plots / "review_length_distribution.png")
        plot_aspect_f1(selected_test_metrics, plots / "aspect_f1.png")
        plot_sentiment_confusion(selected_test_metrics, plots / "sentiment_confusion.png")
        plot_threshold_curves(threshold_curves, plots / "threshold_f1.png")
        plot_pr_curves(dev, dev_raw, plots / "pr_curves_dev.png")
        plot_model_comparison({"Rule": rule_metrics, "LinearSVM": svm_metrics, "TF-IDF LR": test_metrics}, plots / "model_comparison.png")
        if challenge:
            plot_challenge_slices({"Rule": rule_challenge_metrics, "LinearSVM": svm_challenge_metrics, "TF-IDF LR": challenge_metrics}, plots / "challenge_performance.png")
        if learning:
            plot_learning_curve(learning, plots / "learning_curve.png")

    print(json.dumps({
        "model": str(out / "baseline.joblib"),
        "selected_on_dev": selected_name,
        "test_pair_macro_f1_strict_union": selected_test_metrics["pair_macro_f1_strict_union"],
        "challenge_slices": challenge_metrics,
        "warning": metrics["warning"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
