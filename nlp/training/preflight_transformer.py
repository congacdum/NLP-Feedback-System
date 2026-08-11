"""Fail-closed dynamic pre-training validation for Transformer ABSA.

This command deliberately reads Train/Dev only.  It never tunes/evaluates Test
and never launches the full training protocol.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from nlp.evaluation.metrics import evaluate_records
from nlp.models.multitask_transformer import MultiTaskABSA
from nlp.preprocessing.text import normalized_hash_text
from nlp.preprocessing.segmenter import VnCoreNLPSegmenter
from nlp.schema import ASPECTS, SENTIMENTS, validate_runtime_result
from nlp.training.train_transformer import ABSADataset, class_weights, prediction_payload, read_jsonl, seed_all

ROOT = Path(__file__).resolve().parents[2]
BACKBONE = "vinai/phobert-base-v2"
WEIGHTING_STRATEGY = "raw_negative_positive_aspect__normalized_inverse_frequency_sentiment"
TAXONOMY_VERSION = "absa-v1"


def finite(value: torch.Tensor | None) -> bool:
    return value is not None and bool(torch.isfinite(value).all())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def static_audit(rows: list[dict]) -> dict[str, Any]:
    malformed: list[dict] = []
    aspects, sentiments, no_aspect = Counter(), Counter(), 0
    hashes: dict[str, str] = {}
    duplicates: list[list[str]] = []
    for i, row in enumerate(rows):
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            malformed.append({"row": i, "reason": "empty text"})
        annotations = row.get("annotations", [])
        if not isinstance(annotations, list):
            malformed.append({"row": i, "reason": "annotations is not list"})
            continue
        if not annotations:
            no_aspect += 1
        seen = set()
        for ann in annotations:
            if not isinstance(ann, dict) or ann.get("aspect") not in ASPECTS or ann.get("sentiment") not in SENTIMENTS:
                malformed.append({"row": i, "reason": f"invalid annotation: {ann}"})
                continue
            if ann["aspect"] in seen:
                malformed.append({"row": i, "reason": f"duplicate aspect: {ann['aspect']}"})
            seen.add(ann["aspect"]); aspects[ann["aspect"]] += 1; sentiments[ann["sentiment"]] += 1
        norm = normalized_hash_text(str(text or ""))
        h = hashlib.sha256(norm.encode()).hexdigest()
        if h in hashes: duplicates.append([hashes[h], str(row.get("id", i))])
        else: hashes[h] = str(row.get("id", i))
    return {"rows": len(rows), "no_aspect": no_aspect, "aspect_distribution": dict(aspects), "sentiment_distribution": dict(sentiments), "malformed_count": len(malformed), "malformed": malformed[:20], "exact_duplicates_within_split": duplicates[:20], "exact_duplicate_count": len(duplicates)}


def cross_split_duplicates(train: list[dict], dev: list[dict]) -> list[list[str]]:
    train_hash = {hashlib.sha256(normalized_hash_text(r["text"]).encode()).hexdigest(): str(r.get("id")) for r in train}
    return [[train_hash[h], str(r.get("id"))] for r in dev if (h := hashlib.sha256(normalized_hash_text(r["text"]).encode()).hexdigest()) in train_hash]


def _simhash64(norm: str) -> int:
    """Match the project leakage validator's conservative candidate filter."""
    tokens = norm.split()
    features = tokens if len(tokens) < 2 else tokens + [f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)]
    vector = [0] * 64
    for feature in features:
        digest = int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(64):
            vector[bit] += 1 if (digest >> bit) & 1 else -1
    return sum((1 << bit) for bit, value in enumerate(vector) if value >= 0)


def _shingles(norm: str) -> set[str]:
    tokens = norm.split()
    return set(tokens) if len(tokens) <= 2 else {" ".join(tokens[i:i + 2]) for i in range(len(tokens) - 1)}


def cross_split_near_duplicates(train: list[dict], dev: list[dict], threshold: float = 0.90) -> list[dict[str, Any]]:
    """Report critical Train/Dev near duplicates without reading held-out Test."""
    bands: dict[tuple[int, int], list[tuple[str, int, set[str], str]]] = defaultdict(list)
    findings: list[dict[str, Any]] = []
    for row in train:
        text = str(row.get("text") or "")
        norm = normalized_hash_text(text)
        if len(norm.split()) < 5:
            continue
        sim, shingles = _simhash64(norm), _shingles(norm)
        for band in range(4):
            bands[(band, (sim >> (band * 16)) & 0xFFFF)].append((str(row.get("id")), sim, shingles, text))
    for row in dev:
        text = str(row.get("text") or "")
        norm = normalized_hash_text(text)
        if len(norm.split()) < 5:
            continue
        sim, shingles = _simhash64(norm), _shingles(norm)
        candidates: dict[str, tuple[str, int, set[str], str]] = {}
        for band in range(4):
            for item in bands.get((band, (sim >> (band * 16)) & 0xFFFF), []):
                candidates[item[0]] = item
        for train_id, train_sim, train_shingles, train_text in candidates.values():
            if (sim ^ train_sim).bit_count() > 3:
                continue
            union = shingles | train_shingles
            jaccard = len(shingles & train_shingles) / max(1, len(union))
            if jaccard >= threshold:
                findings.append({"train_id": train_id, "dev_id": str(row.get("id")), "jaccard": round(jaccard, 4), "train_text": train_text[:180], "dev_text": text[:180]})
    return findings


def weight_report(train: list[dict]) -> dict[str, Any]:
    n = len(train); pos = Counter(a["aspect"] for r in train for a in r.get("annotations", [])); sent = Counter(a["sentiment"] for r in train for a in r.get("annotations", []))
    raw_pos = {a: (n - pos[a]) / max(pos[a], 1) for a in ASPECTS}
    raw_sent = {s: sum(sent.values()) / max(sent[s], 1) for s in SENTIMENTS}
    mean = sum(raw_sent.values()) / len(raw_sent)
    sent_weights = {s: raw_sent[s] / mean for s in SENTIMENTS}
    values = [*raw_pos.values(), *sent_weights.values()]
    return {"strategy": WEIGHTING_STRATEGY, "aspects": {a: {"positive_count": pos[a], "negative_count": n - pos[a], "prevalence": pos[a] / n, "raw_pos_weight": raw_pos[a]} for a in ASPECTS}, "sentiment_weights": sent_weights, "finite_positive": all(math.isfinite(v) and v > 0 for v in values)}


def stack(dataset: ABSADataset, indices: list[int], device: torch.device) -> dict[str, torch.Tensor]:
    keys = ("input_ids", "attention_mask", "aspect_targets", "sentiment_targets")
    return {key: torch.stack([dataset[i][key] for i in indices]).to(device) for key in keys}


class IndexedDataset(torch.utils.data.Dataset):
    """Keep original row indices solely for a useful fail-fast error report."""
    def __init__(self, dataset: ABSADataset, indices: list[int] | None = None):
        self.dataset = dataset
        self.indices = indices if indices is not None else list(range(len(dataset)))

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, item: int) -> dict[str, torch.Tensor]:
        original_index = self.indices[item]
        result = dict(self.dataset[original_index])
        result["_preflight_index"] = torch.tensor(original_index, dtype=torch.long)
        return result


def batch_meta(rows: list[dict], indices: list[int]) -> dict[str, Any]:
    return {"ids": [rows[i].get("id", i) for i in indices], "annotations": [rows[i].get("annotations", []) for i in indices]}


def assert_output(name: str, out, meta: dict[str, Any]) -> dict[str, Any]:
    fields = {"aspect_logits": out.aspect_logits, "sentiment_logits": out.sentiment_logits, "aspect_loss": out.aspect_loss, "sentiment_loss": out.sentiment_loss, "total_loss": out.loss}
    bad = [k for k, v in fields.items() if not finite(v)]
    if bad:
        raise FloatingPointError(f"{name}: non-finite {bad}; meta={meta}")
    return {"status": "PASS", "aspect_loss": float(out.aspect_loss.detach()), "sentiment_loss": float(out.sentiment_loss.detach()), "total_loss": float(out.loss.detach()), "logit_min": float(torch.minimum(out.aspect_logits.min(), out.sentiment_logits.min()).detach()), "logit_max": float(torch.maximum(out.aspect_logits.max(), out.sentiment_logits.max()).detach())}


def gradient_stats(model: torch.nn.Module) -> dict[str, float]:
    norms = [float(p.grad.detach().norm()) for p in model.parameters() if p.grad is not None]
    if not norms or not all(math.isfinite(n) for n in norms):
        raise FloatingPointError("non-finite or missing gradients")
    return {"gradient_norm_mean": sum(norms) / len(norms), "gradient_norm_max_parameter": max(norms), "gradient_norm_total": math.sqrt(sum(x * x for x in norms))}


def select_indices(rows: list[dict], predicate, count: int = 2) -> list[int]:
    found = [i for i, r in enumerate(rows) if predicate(r)]
    if not found: raise ValueError("required preflight case has no matching Train sample")
    return (found * ((count + len(found) - 1) // len(found)))[:count]


def loss_matrix(model, dataset, rows, device, pw, sw) -> dict[str, Any]:
    rare_plus_no_aspect = (
        select_indices(rows, lambda r: any(a["aspect"] in {"customer_service", "other"} for a in r.get("annotations", [])), 1)
        + select_indices(rows, lambda r: not r.get("annotations"), 1)
    )
    cases = {
        "normal": select_indices(rows, lambda r: bool(r.get("annotations"))),
        "all_no_aspect": select_indices(rows, lambda r: not r.get("annotations")),
        "zero_valid_sentiment": select_indices(rows, lambda r: not r.get("annotations")),
        "single_aspect": select_indices(rows, lambda r: len(r.get("annotations", [])) == 1),
        "multi_aspect": select_indices(rows, lambda r: len(r.get("annotations", [])) >= 2),
        "customer_service": select_indices(rows, lambda r: any(a["aspect"] == "customer_service" for a in r.get("annotations", []))),
        "other": select_indices(rows, lambda r: any(a["aspect"] == "other" for a in r.get("annotations", []))),
        "mixed_sentiment": select_indices(rows, lambda r: any(a["sentiment"] == "mixed" for a in r.get("annotations", []))),
        "rare_aspect_no_aspect_mixed": rare_plus_no_aspect,
    }
    report = {}
    model.eval()
    with torch.inference_mode():
        for name, indices in cases.items():
            batch = stack(dataset, indices, device); meta = batch_meta(rows, indices)
            out = model(**batch, aspect_pos_weight=pw, sentiment_class_weight=sw)
            report[name] = assert_output(name, out, meta)
    return report


def optimizer_steps(model, loader, rows, device, pw, sw, steps: int, *, rare_only: bool = False) -> dict[str, Any]:
    model.train(); optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5); history = []; peak = 0
    for step, raw in enumerate(loader, 1):
        if step > steps: break
        indices = raw.pop("_preflight_index").tolist()
        meta = batch_meta(rows, indices); meta["rare_only"] = rare_only
        batch = {k: v.to(device) for k, v in raw.items()}; optimizer.zero_grad(set_to_none=True)
        out = model(**batch, aspect_pos_weight=pw, sentiment_class_weight=sw)
        item = assert_output(f"optimizer_step={step}", out, meta)
        try:
            out.loss.backward(); item.update(gradient_stats(model))
        except FloatingPointError as exc:
            raise FloatingPointError(f"{exc}; optimizer_step={step}; meta={meta}") from exc
        if not all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None): raise FloatingPointError(f"non-finite gradients at step {step}; meta={meta}")
        optimizer.step()
        if not all(torch.isfinite(p).all() for p in model.parameters()): raise FloatingPointError(f"non-finite parameters at step {step}; meta={meta}")
        if device.type == "cuda": peak = max(peak, int(torch.cuda.max_memory_allocated(device))); item.update({"gpu_allocated": int(torch.cuda.memory_allocated(device)), "gpu_reserved": int(torch.cuda.memory_reserved(device))})
        history.append(item)
    if len(history) < steps: raise RuntimeError(f"only {len(history)} of requested {steps} optimizer steps ran")
    losses = [x["total_loss"] for x in history]
    return {"status": "PASS", "steps": len(history), "start_loss": losses[0], "end_loss": losses[-1], "max_loss": max(losses), "peak_allocated_bytes": peak, "gradient_norm_mean": sum(x["gradient_norm_total"] for x in history) / len(history), "gradient_norm_max": max(x["gradient_norm_max_parameter"] for x in history), "tail": history[-5:]}


def coverage_subset(rows: list[dict], n: int) -> list[int]:
    selected: list[int] = []; seen = set()
    for aspect in ASPECTS:
        for i, r in enumerate(rows):
            if i not in seen and any(a["aspect"] == aspect for a in r.get("annotations", [])):
                selected.append(i); seen.add(i); break
    for i, r in enumerate(rows):
        if i not in seen and not r.get("annotations"):
            selected.append(i); seen.add(i); break
    for i in range(len(rows)):
        if len(selected) >= n: break
        if i not in seen: selected.append(i); seen.add(i)
    return selected


def mini_overfit(model, dataset, rows, device, pw, sw, n: int) -> tuple[dict[str, Any], list[int]]:
    indices = coverage_subset(rows, n); loader = DataLoader(torch.utils.data.Subset(dataset, indices), batch_size=2, shuffle=True)
    eval_loader = DataLoader(torch.utils.data.Subset(dataset, indices), batch_size=2, shuffle=False)
    def evaluate_subset():
        model.eval(); losses=[]; preds=[]
        with torch.inference_mode():
            for raw in eval_loader:
                batch={k:v.to(device) for k,v in raw.items()}; out=model(**batch,aspect_pos_weight=pw,sentiment_class_weight=sw)
                assert_output("mini_overfit_eval",out,{})
                losses.append(float(out.loss.detach())); preds.extend(prediction_payload(out.aspect_logits,out.sentiment_logits,{a:0.5 for a in ASPECTS}))
        return sum(losses)/len(losses), evaluate_records([rows[i] for i in indices],preds)["pair_macro_f1_strict_union"]
    initial_loss, initial_metric = evaluate_subset()
    model.train(); opt = torch.optim.AdamW(model.parameters(), lr=2e-5); losses=[]
    for _epoch in range(3):
        for raw in loader:
            batch={k:v.to(device) for k,v in raw.items()}; opt.zero_grad(set_to_none=True); out=model(**batch,aspect_pos_weight=pw,sentiment_class_weight=sw); assert_output("mini_overfit",out,{"epoch":_epoch}); out.loss.backward(); gradient_stats(model); opt.step(); losses.append(float(out.loss.detach()))
    final_loss, final_metric = evaluate_subset()
    result={"status":"PASS" if final_loss < initial_loss * 0.90 else "FAIL", "samples":len(indices), "start_loss":initial_loss, "end_loss":final_loss, "min_step_loss":min(losses), "start_metric":initial_metric, "end_metric":final_metric}
    return result, indices


def offline_infer(smoke_dir: Path, vnc_dir: Path, texts: list[str]) -> list[dict]:
    """Use a fresh Python/JVM process: pyjnius permits one JVM per process."""
    code = (
        "import json; from nlp.inference.transformer_analyzer import TransformerAnalyzer; "
        "from nlp.schema import validate_runtime_result; "
        f"a=TransformerAnalyzer({str(smoke_dir)!r},vncorenlp_dir={str(vnc_dir)!r},allow_experimental=True); "
        f"print(json.dumps([validate_runtime_result(a.analyze(x)) for x in {texts!r}],ensure_ascii=False))"
    )
    run = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
    if run.returncode:
        raise RuntimeError(f"offline local-only inference failed: {run.stderr[-1000:]}")
    return json.loads(run.stdout.strip().splitlines()[-1])


def save_and_load(model, tokenizer, thresholds, max_length: int, smoke_dir: Path, vnc_dir: Path) -> dict[str, Any]:
    if smoke_dir.exists(): shutil.rmtree(smoke_dir)
    smoke_dir.mkdir(parents=True); torch.save(model.state_dict(), smoke_dir / "model.pt"); tokenizer.save_pretrained(smoke_dir / "tokenizer"); model.encoder.config.save_pretrained(smoke_dir / "encoder_config")
    (smoke_dir / "thresholds.json").write_text(json.dumps(thresholds), encoding="utf8")
    (smoke_dir / "training_manifest.json").write_text(json.dumps({"backbone_name": BACKBONE, "backbone_key":"phobert", "max_length":max_length, "taxonomy":{"aspects":list(ASPECTS),"sentiments":list(SENTIMENTS)}, "experimental_only":True,"scientific_final":False}), encoding="utf8")
    (smoke_dir / "training_config.json").write_text(json.dumps({"backbone_name": BACKBONE, "max_length": max_length}), encoding="utf8")
    result=offline_infer(smoke_dir, vnc_dir, ["\u004d\u1edbi m\u1eb7c hai h\u00f4m m\u00e0 \u0111\u01b0\u1eddng ch\u1ec9 \u0111\u00e3 bung h\u1ebft."])[0]
    return {"status":"PASS","artifact":str(smoke_dir),"inference_status":result["status"]}


def run_regression_tests(output_dir: Path) -> dict[str, Any]:
    """Run regression tests in a run-owned temp directory.

    Windows can deny access to a stale system ``pytest-of-<user>`` directory.
    That is an infrastructure concern, so preflight keeps test artefacts under
    its own output directory instead of depending on the global temp location.
    """
    basetemp = output_dir / "pytest-regression"
    command = [
        sys.executable, "-m", "pytest",
        "tests/nlp/test_multitask_loss.py", "tests/nlp/test_transformer_preflight.py",
        "-q", "--basetemp", str(basetemp),
    ]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
    return {"status": "PASS" if run.returncode == 0 else "FAIL", "command": " ".join(command), "output_tail": (run.stdout + run.stderr)[-2000:]}


def main() -> None:
    p=argparse.ArgumentParser(description="Run dynamic fail-closed Transformer ABSA preflight; Train/Dev only.")
    p.add_argument("--train",type=Path,default=ROOT/"nlp/data/experimental/train.jsonl"); p.add_argument("--dev",type=Path,default=ROOT/"nlp/data/experimental/dev.jsonl")
    p.add_argument("--vncorenlp-dir",type=Path,required=True); p.add_argument("--output-dir",type=Path,default=ROOT/"model_artifacts"); p.add_argument("--cuda-steps",type=int,default=100); p.add_argument("--forward-steps",type=int,default=32); p.add_argument("--mini-samples",type=int,default=256)
    args=p.parse_args(); seed_all(42); train,dev=read_jsonl(args.train),read_jsonl(args.dev); device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    static={"train":static_audit(train),"dev":static_audit(dev),"cross_split_exact_duplicates":cross_split_duplicates(train,dev),"cross_split_near_duplicates":cross_split_near_duplicates(train,dev)}; weights=weight_report(train)
    static_pass=static["train"]["malformed_count"]==0 and static["dev"]["malformed_count"]==0 and not static["cross_split_exact_duplicates"] and not static["cross_split_near_duplicates"]
    report:dict[str,Any]={"version":2,"backbone":BACKBONE,"dataset":{"train":str(args.train.resolve()),"dev":str(args.dev.resolve())},"training_contract":{"train_sha256":file_sha256(args.train),"dev_sha256":file_sha256(args.dev),"backbone_name":BACKBONE,"max_length":256,"taxonomy_version":TAXONOMY_VERSION,"taxonomy":{"aspects":list(ASPECTS),"sentiments":list(SENTIMENTS)},"weighting_strategy":WEIGHTING_STRATEGY},"static":static,"static_status":"PASS" if static_pass else "FAIL","class_weights":weights,"cuda":{"available":torch.cuda.is_available(),"device":str(device),"torch":torch.__version__,"torch_cuda":torch.version.cuda,"gpu":torch.cuda.get_device_name(0) if torch.cuda.is_available() else None},"warnings":[]}
    if not torch.cuda.is_available(): raise SystemExit("PRE-FLIGHT FAIL: CUDA is required")
    from transformers import AutoTokenizer
    seg=VnCoreNLPSegmenter(args.vncorenlp_dir); tokenizer=AutoTokenizer.from_pretrained(BACKBONE,use_fast=False); dataset=ABSADataset(train,tokenizer,256,seg); dev_ds=ABSADataset(dev[:32],tokenizer,256,seg)
    model=MultiTaskABSA(BACKBONE).to(device); pw,sw=class_weights(train,device)
    report["loss_edge_cases"]=loss_matrix(model,dataset,train,device,pw,sw)
    report["forward_backward"]=optimizer_steps(model,DataLoader(IndexedDataset(dataset),batch_size=2,shuffle=True),train,device,pw,sw,args.forward_steps)
    rare_indices=[i for i,r in enumerate(train) if any(a["aspect"] in {"customer_service","other"} for a in r.get("annotations",[]))]
    report["gradient_stress"]=optimizer_steps(model,DataLoader(IndexedDataset(dataset,rare_indices),batch_size=2,shuffle=True),train,device,pw,sw,min(20,max(1,len(rare_indices)//2)),rare_only=True)
    report["cuda_stress"]=optimizer_steps(model,DataLoader(IndexedDataset(dataset),batch_size=2,shuffle=True),train,device,pw,sw,args.cuda_steps)
    report["mini_overfit"],_ = mini_overfit(model,dataset,train,device,pw,sw,args.mini_samples)
    model.eval()
    with torch.inference_mode():
        first = stack(dev_ds, [0], device)
        first_out = model(first["input_ids"], first["attention_mask"])
        payload=prediction_payload(first_out.aspect_logits, first_out.sentiment_logits,{a:0.5 for a in ASPECTS})[0]
    raw=[]
    with torch.inference_mode():
        for i in range(min(32,len(dev_ds))):
            one=stack(dev_ds,[i],device); out=model(one["input_ids"],one["attention_mask"])
            raw.append(prediction_payload(out.aspect_logits,out.sentiment_logits,{a:0.5 for a in ASPECTS})[0])
    try:
        checked=[validate_runtime_result(item) for item in raw]
        # Force the two threshold boundaries without inventing labels: this
        # validates both no-aspect and multi-aspect serialization paths.
        low=validate_runtime_result(prediction_payload(first_out.aspect_logits,first_out.sentiment_logits,{a:0.0 for a in ASPECTS})[0])
        high=validate_runtime_result(prediction_payload(first_out.aspect_logits,first_out.sentiment_logits,{a:1.0 for a in ASPECTS})[0])
        values=[score for item in raw for score in [*item["aspect_scores"].values(), *(score for per_aspect in item["sentiment_scores"].values() for score in per_aspect.values())]]
        mini_status="PASS" if all(math.isfinite(float(score)) for score in values) and len(low["aspects"]) > 1 and high["status"] == "no_aspect" else "FAIL"
        report["mini_dev"]={"status":mini_status,"rows_checked":len(checked),"default_output":payload,"forced_multi_aspect_count":len(low["aspects"]),"forced_no_aspect_status":high["status"]}
    except (ValueError, KeyError, TypeError) as exc:
        report["mini_dev"]={"status":"FAIL","error":f"{type(exc).__name__}: {exc}"}
    # Mini Dev only verifies inference/schema. Full-run Dev performs the sole
    # model threshold selection, so this smoke artifact keeps neutral defaults.
    thresholds={a:0.5 for a in ASPECTS}
    smoke_dir=args.output_dir/"preflight_smoke_phobert"
    report["artifact_save_load"]=save_and_load(model,tokenizer,thresholds,256,smoke_dir,args.vncorenlp_dir)
    cases=["\u004d\u1edbi m\u1eb7c hai h\u00f4m m\u00e0 \u0111\u01b0\u1eddng ch\u1ec9 \u0111\u00e3 bung h\u1ebft.","S\u1ea3n ph\u1ea9m \u0111\u1eb9p nh\u01b0ng giao h\u00e0ng l\u00e2u kinh kh\u1ee7ng.","Kh\u00f4ng h\u1ec1 \u0111\u00e1ng ti\u1ec1n ch\u00fat n\u00e0o.","H\u1ed9p m\u00f3p m\u00e9o nh\u01b0ng \u0111\u1ed3 b\u00ean trong v\u1eabn nguy\u00ean v\u1eb9n.","Nh\u1eafn t\u1eeb s\u00e1ng m\u00e0 shop kh\u00f4ng tr\u1ea3 l\u1eddi.","S\u1ea3n ph\u1ea9m kh\u00f4ng t\u1ec7."]
    report["semantic_smoke"]={"status":"PASS","results":offline_infer(smoke_dir,args.vncorenlp_dir,cases)}
    report["regression_tests"]=run_regression_tests(args.output_dir)
    critical=[static["train"]["malformed_count"]==0,static["dev"]["malformed_count"]==0,not static["cross_split_exact_duplicates"],not static["cross_split_near_duplicates"],weights["finite_positive"],all(x["status"]=="PASS" for x in report["loss_edge_cases"].values()),report["forward_backward"]["status"]=="PASS",report["gradient_stress"]["status"]=="PASS",report["cuda_stress"]["status"]=="PASS",report["mini_overfit"]["status"]=="PASS",report["mini_dev"]["status"]=="PASS",report["artifact_save_load"]["status"]=="PASS",report["semantic_smoke"]["status"]=="PASS",report["regression_tests"]["status"]=="PASS"]
    if max(v["raw_pos_weight"] for v in weights["aspects"].values())>100: report["warnings"].append("Severe class imbalance: raw pos_weight is high for sparse aspects; retained because dynamic gradients remained finite.")
    report["overall_preflight"]="PASS" if all(critical) else "FAIL"; report["full_training_allowed"]=report["overall_preflight"]=="PASS"; args.output_dir.mkdir(parents=True,exist_ok=True)
    report_path=args.output_dir/"preflight_transformer_report.json"
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    try:
        from nlp.training.train_transformer import validate_preflight_gate
        validate_preflight_gate(report_path,args.train,args.dev,BACKBONE,256)
        report["trainer_guard"]={"status":"PASS","checks":["report exists","overall PASS","canonical paths","dataset SHA-256","taxonomy","backbone","max length","weighting strategy"]}
    except Exception as exc:
        report["trainer_guard"]={"status":"FAIL","error":f"{type(exc).__name__}: {exc}"}; report["overall_preflight"]="FAIL"; report["full_training_allowed"]=False
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8"); (args.output_dir/"preflight_transformer_report.md").write_text(f"# Transformer dynamic preflight\n\n**{report['overall_preflight']}**\n\n```json\n{json.dumps(report,ensure_ascii=False,indent=2)}\n```\n",encoding="utf8")
    print(json.dumps({"overall_preflight":report["overall_preflight"],"full_training_allowed":report["full_training_allowed"]},ensure_ascii=False))

if __name__=="__main__": main()
