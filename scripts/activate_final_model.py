from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and prepare a frozen Transformer artifact for runtime activation")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "model_artifacts")
    parser.add_argument("--env-out", type=Path, default=ROOT / "data" / "final_model.env")
    parser.add_argument("--allow-experimental", action="store_true", help="Allow an explicitly labelled non-scientific experimental artifact to run locally.")
    args = parser.parse_args()
    artifact = args.artifact.resolve()
    required = [artifact / "model.pt", artifact / "thresholds.json", artifact / "training_manifest.json", artifact / "tokenizer", artifact / "encoder_config", artifact / "evaluation" / "metrics.json", artifact / "final_evaluation.lock"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Artifact is not a finalized deployable model; missing:\n- " + "\n- ".join(missing))
    manifest = json.loads((artifact / "training_manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((artifact / "evaluation" / "metrics.json").read_text(encoding="utf-8"))
    scientific_final = metrics.get("scientific_final") is True
    if not scientific_final and not args.allow_experimental:
        raise SystemExit("Refusing activation: artifact is non-scientific. Pass --allow-experimental only for a clearly labelled local experimental runtime.")
    taxonomy = manifest.get("taxonomy", {})
    if taxonomy.get("aspects") != ["product_quality", "delivery", "customer_service", "packaging", "price", "other"] or taxonomy.get("sentiments") != ["positive", "neutral", "negative", "mixed"]:
        raise SystemExit("Refusing activation: artifact taxonomy does not match the frozen project schema")
    thresholds = json.loads((artifact / "thresholds.json").read_text(encoding="utf-8"))
    if set(thresholds) != set(taxonomy["aspects"]):
        raise SystemExit("Refusing activation: thresholds.json does not contain one threshold per aspect")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    activation = {"artifact": str(artifact), "model_version": artifact.name, "scientific_final": scientific_final, "experimental_only": not scientific_final, "primary_metric": metrics.get("primary_metric"), "test": metrics.get("test", {}), "runtime_backend": "transformer"}
    (args.output_dir / "active_transformer.json").write_text(json.dumps(activation, ensure_ascii=False, indent=2), encoding="utf-8")
    args.env_out.parent.mkdir(parents=True, exist_ok=True)
    args.env_out.write_text("\n".join(["NLP_BACKEND=transformer", f"TRANSFORMER_ARTIFACT={artifact}", f"EVALUATION_ARTIFACT={artifact}", "REQUIREMENTS_FILE=requirements-transformer-runtime.txt", ""]), encoding="utf-8")
    print(json.dumps({"status": "ready", "scientific_final": scientific_final, "activation": str(args.output_dir / "active_transformer.json"), "env_snippet": str(args.env_out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
