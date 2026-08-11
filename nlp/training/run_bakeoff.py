from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEEDS = (42, 52, 62)
BACKBONES = ("phobert", "bamibert")


def main() -> None:
    p = argparse.ArgumentParser(description="Train selected seeds/backbones on Train/Dev only; Test is never opened")
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--train", type=Path, default=ROOT / "nlp/data/gold/train.jsonl")
    p.add_argument("--dev", type=Path, default=ROOT / "nlp/data/gold/dev.jsonl")
    p.add_argument("--vncorenlp-dir", type=Path, default=None)
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--backbones", nargs="+", choices=BACKBONES, default=list(BACKBONES))
    p.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    p.add_argument("--output-dir", type=Path, default=ROOT / "model_artifacts")
    p.add_argument("--device", default="auto")
    args = p.parse_args()
    if not args.train.exists() or not args.dev.exists():
        raise SystemExit("Gold Train/Dev missing. Do not run a Transformer bakeoff on the demo fixture as if it were final data.")

    if args.config:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        for key, value in config.items():
            if not hasattr(args, key): raise SystemExit(f"Unknown bakeoff config key: {key}")
            if getattr(args, key) == p.get_default(key): setattr(args, key, value)
    scores = defaultdict(list)
    artifacts = []
    for backbone in args.backbones:
        for seed in args.seeds:
            out = args.output_dir / f"{backbone}_absa_seed{seed}"
            cmd = [
                sys.executable, "-m", "nlp.training.train_transformer",
                "--backbone", backbone,
                "--train", str(args.train),
                "--dev", str(args.dev),
                "--out", str(out),
                "--epochs", str(args.epochs),
                "--batch-size", str(args.batch_size),
                "--seed", str(seed),
                "--device", str(args.device),
            ]
            if backbone == "phobert":
                if args.vncorenlp_dir is None:
                    raise SystemExit("PhoBERT bakeoff requires --vncorenlp-dir")
                cmd += ["--vncorenlp-dir", str(args.vncorenlp_dir)]
            subprocess.run(cmd, cwd=ROOT, check=True)
            manifest = json.loads((out / "training_manifest.json").read_text(encoding="utf-8"))
            score = float(manifest["best_dev_pair_macro_f1_strict_union"])
            scores[backbone].append(score)
            artifacts.append({"backbone": backbone, "seed": seed, "artifact": str(out), "best_dev_pair_macro_f1_strict_union": score})

    summary = {}
    for backbone, vals in scores.items():
        mean = sum(vals) / len(vals)
        variance = sum((x - mean) ** 2 for x in vals) / max(1, len(vals) - 1)
        summary[backbone] = {"mean_dev_pair_macro_f1_strict_union": mean, "std": variance ** 0.5, "seeds": list(args.seeds)}
    winner = max(summary, key=lambda b: summary[b]["mean_dev_pair_macro_f1_strict_union"])
    result = {
        "selection_uses_test": False,
        "primary_selection_metric": "mean best Dev strict-union Pair Macro-F1 across seeds",
        "artifacts": artifacts,
        "backbones": summary,
        "winner_backbone": winner,
        "next_step": "Freeze the winning architecture/protocol, then run final held-out evaluation without tuning on Test.",
    }
    path = args.output_dir / "transformer_bakeoff_summary.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
