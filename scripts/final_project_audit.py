from __future__ import annotations

import argparse
import compileall
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "PROJECT_KNOWLEDGE.md",
    "AI_CHANGELOG.md",
    "Dockerfile",
    "docker-compose.yml",
    "START.bat",
    "START_WITH_RASA.bat",
    "STOP.bat",
    "app/main.py",
    "app/services/nlp_service.py",
    "app/services/feedback_service.py",
    "nlp/schema.py",
    "nlp/models/multitask_transformer.py",
    "nlp/training/train_transformer.py",
    "nlp/training/run_bakeoff.py",
    "nlp/training/finalize_transformer.py",
    "nlp/evaluation/metrics.py",
    "docs/ANNOTATION_GUIDELINE.md",
    "docs/DATA_SOURCES_AND_MAPPING.md",
    "docs/ARCHITECTURE.md",
    "docs/MODEL_CARD.md",
    "model_artifacts/baseline_absa_v0/baseline.joblib",
    "model_artifacts/baseline_absa_v0/linear_svm_baseline.joblib",
    "model_artifacts/baseline_absa_v0/evaluation/metrics.json",
    "scripts/export_annotation_batch.py",
    "scripts/import_verified_annotations.py",
    "scripts/annotation_agreement.py",
    "scripts/split_verified_custom.py",
    "scripts/build_final_gold_dataset.py",
    "requirements-transformer-runtime.txt",
]


def run(cmd: list[str], *, timeout: int = 180) -> dict:
    try:
        p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {"cmd": cmd, "returncode": p.returncode, "stdout": p.stdout[-12000:], "stderr": p.stderr[-12000:]}
    except Exception as exc:
        return {"cmd": cmd, "returncode": -999, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}


def check_json(path: Path) -> str | None:
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return None
    except Exception as exc:
        return f"{path.relative_to(ROOT)}: {type(exc).__name__}: {exc}"


def collect_files() -> list[Path]:
    ignore_parts = {"__pycache__", ".pytest_cache", ".git"}
    return [p for p in ROOT.rglob("*") if p.is_file() and not any(part in ignore_parts for part in p.parts)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-pytest", action="store_true")
    args = ap.parse_args()
    checks: list[dict] = []

    missing = [x for x in REQUIRED if not (ROOT / x).exists()]
    checks.append({"name": "required_files", "status": "PASS" if not missing else "FAIL", "details": missing})

    compile_ok = compileall.compile_dir(ROOT / "app", quiet=1) and compileall.compile_dir(ROOT / "nlp", quiet=1) and compileall.compile_dir(ROOT / "scripts", quiet=1)
    checks.append({"name": "python_compile", "status": "PASS" if compile_ok else "FAIL", "details": None})

    dataset = run([
        sys.executable, "scripts/check_dataset.py",
        "nlp/data/demo/train.jsonl", "nlp/data/demo/dev.jsonl", "nlp/data/demo/test.jsonl",
    ])
    checks.append({"name": "demo_dataset_validation", "status": "PASS" if dataset["returncode"] == 0 else "FAIL", "details": dataset})

    if args.skip_pytest:
        checks.append({"name": "pytest", "status": "NOT_RUN", "details": "--skip-pytest"})
    else:
        tests = run([sys.executable, "-m", "pytest", "-q"], timeout=240)
        checks.append({"name": "pytest", "status": "PASS" if tests["returncode"] == 0 else "FAIL", "details": tests})

    json_errors = []
    for rel in [
        "data/demo_products.json",
        "model_artifacts/baseline_absa_v0/thresholds.json",
        "model_artifacts/baseline_absa_v0/evaluation/metrics.json",
        "model_artifacts/baseline_absa_v0/evaluation/evaluation_manifest.json",
    ]:
        err = check_json(ROOT / rel)
        if err:
            json_errors.append(err)
    checks.append({"name": "json_artifacts", "status": "PASS" if not json_errors else "FAIL", "details": json_errors})

    yaml_errors = []
    try:
        import yaml
        compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
        services = set((compose or {}).get("services", {}))
        if not {"app", "rasa", "rasa-actions"}.issubset(services):
            yaml_errors.append(f"docker-compose missing services: {sorted({'app','rasa','rasa-actions'} - services)}")
        for rel in ["rasa_bot/config.yml", "rasa_bot/domain.yml", "rasa_bot/endpoints.yml", "rasa_bot/credentials.yml", "rasa_bot/data/nlu.yml", "rasa_bot/data/rules.yml"]:
            yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
    except Exception as exc:
        yaml_errors.append(f"{type(exc).__name__}: {exc}")
    checks.append({"name": "yaml_static_parse", "status": "PASS" if not yaml_errors else "FAIL", "details": yaml_errors})

    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    endpoints_text = (ROOT / "rasa_bot/endpoints.yml").read_text(encoding="utf-8")
    start_rasa = (ROOT / "START_WITH_RASA.bat").read_text(encoding="utf-8")
    static_issues = []
    if "./rasa_bot:/app" not in compose_text:
        static_issues.append("Rasa project volume missing")
    if 'http://rasa-actions:5055/webhook' not in endpoints_text:
        static_issues.append("Rasa action endpoint does not target compose service name")
    if "rasa train" not in start_rasa:
        static_issues.append("START_WITH_RASA.bat does not train before run")
    if "TRANSFORMER_ARTIFACT" not in compose_text or "REQUIREMENTS_FILE" not in compose_text:
        static_issues.append("Compose does not expose the frozen Transformer/runtime dependency configuration")
    analyzer_text = (ROOT / "nlp/inference/transformer_analyzer.py").read_text(encoding="utf-8")
    if "encoder_config" not in analyzer_text or "local_files_only=True" not in analyzer_text:
        static_issues.append("Frozen Transformer runtime is not guaranteed to load tokenizer/config locally")
    if "40.9" not in (ROOT / "PROJECT_KNOWLEDGE.md").read_text(encoding="utf-8"):
        static_issues.append("PROJECT_KNOWLEDGE missing image-storage constraint")
    checks.append({"name": "critical_static_contracts", "status": "PASS" if not static_issues else "FAIL", "details": static_issues})

    docker = shutil.which("docker")
    if docker:
        docker_check = run([docker, "compose", "config"], timeout=120)
        checks.append({"name": "docker_compose_config", "status": "PASS" if docker_check["returncode"] == 0 else "FAIL", "details": docker_check})
    else:
        checks.append({"name": "docker_compose_config", "status": "NOT_RUN", "details": "Docker executable is not available in the build environment; runtime Docker success is not claimed."})

    files = collect_files()
    large = [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size} for p in files if p.stat().st_size > 25 * 1024 * 1024]
    checks.append({"name": "no_unexpected_large_files_over_25MB", "status": "PASS" if not large else "FAIL", "details": large})

    todos = []
    audit_script = Path(__file__).resolve()
    for p in files:
        if p.resolve() == audit_script:
            continue
        if p.suffix not in {".py", ".html", ".js", ".css", ".yml", ".yaml", ".bat"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for marker in ("TODO", "FIXME"):
            if marker in text:
                todos.append({"path": str(p.relative_to(ROOT)), "marker": marker})
    checks.append({"name": "no_todo_fixme_in_runtime_code", "status": "PASS" if not todos else "WARN", "details": todos})

    scientific_metrics = json.loads((ROOT / "model_artifacts/baseline_absa_v0/evaluation/metrics.json").read_text(encoding="utf-8"))
    metric_integrity = scientific_metrics.get("scientific_final") is False and bool(scientific_metrics.get("warning"))
    checks.append({"name": "demo_metrics_not_misrepresented_as_final", "status": "PASS" if metric_integrity else "FAIL", "details": {"scientific_final": scientific_metrics.get("scientific_final"), "warning": scientific_metrics.get("warning")}})

    n_files = len(files)
    total_bytes = sum(p.stat().st_size for p in files)
    py_lines = 0
    for p in files:
        if p.suffix == ".py":
            try:
                py_lines += len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
            except Exception:
                pass

    hard_fail = any(c["status"] == "FAIL" for c in checks)
    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "overall": "FAIL" if hard_fail else "PASS_WITH_NOT_RUNS" if any(c["status"] == "NOT_RUN" for c in checks) else "PASS",
        "checks": checks,
        "project": {"files": n_files, "bytes": total_bytes, "python_lines": py_lines},
        "environment": {"python": sys.version.split()[0], "docker_available": bool(docker)},
    }
    (ROOT / "FINAL_AUDIT_REPORT.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Final Project Audit Report",
        "",
        f"Generated: `{summary['timestamp_utc']}`",
        "",
        f"Overall: **{summary['overall']}**",
        "",
        f"Files scanned: **{n_files}** · total size: **{total_bytes / 1024 / 1024:.2f} MiB** · Python LOC: **{py_lines}**",
        "",
        "| Check | Status |",
        "|---|---|",
    ]
    for c in checks:
        lines.append(f"| {c['name']} | **{c['status']}** |")
    lines += ["", "## Details", ""]
    for c in checks:
        lines.append(f"### {c['name']} — {c['status']}")
        details = c.get("details")
        if details not in (None, [], {}, ""):
            lines.append("```json")
            lines.append(json.dumps(details, ensure_ascii=False, indent=2, default=str))
            lines.append("```")
        lines.append("")
    lines += [
        "## Interpretation",
        "",
        "`NOT_RUN` is not silently converted to PASS. In particular, Docker runtime is only marked PASS when a Docker executable exists and `docker compose config` can actually run in the audit environment.",
        "",
        "The bundled model metrics are deliberately non-final demo metrics. Scientific Transformer success must be established later from the frozen human-verified gold corpus using the documented Train/Dev/Test protocol.",
    ]
    (ROOT / "FINAL_AUDIT_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"overall": summary["overall"], "checks": {c["name"]: c["status"] for c in checks}}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if hard_fail else 0)


if __name__ == "__main__":
    main()
