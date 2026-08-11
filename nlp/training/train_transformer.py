from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlp.models.multitask_transformer import MultiTaskABSA
from nlp.preprocessing.text import normalize_text
from nlp.preprocessing.segmenter import PHOBERT_PREPROCESSING_VERSION, VnCoreNLPSegmenter, prepare_phobert_text
from nlp.schema import ASPECTS, SENTIMENTS
from nlp.evaluation.metrics import evaluate_records
from nlp.evaluation.thresholds import tune_aspect_thresholds

BACKBONES = {
    "phobert": "vinai/phobert-base-v2",
    "bamibert": "Qualcomm-AI-Research/BamiBERT",
}
CACHE_VERSION = "phobert_wseg_text_v1"
WEIGHTING_STRATEGY = "raw_negative_positive_aspect__normalized_inverse_frequency_sentiment"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def seed_all(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class ABSADataset(Dataset):
    def __init__(self, records, tokenizer, max_length: int, segmenter=None, *, cache_dir: Path | None = None, split_name: str | None = None, dataset_fingerprint: str | None = None, segmenter_signature: str = "none", progress_every: int = 100):
        self.records = records; self.tokenizer = tokenizer; self.max_length = max_length
        self.texts = self._load_or_build_texts(segmenter, cache_dir, split_name, dataset_fingerprint, segmenter_signature, progress_every)

    def _load_or_build_texts(self, segmenter, cache_dir, split_name, dataset_fingerprint, segmenter_signature, progress_every):
        if segmenter is None:
            return [normalize_text(row["text"]) for row in self.records]
        if cache_dir is None or split_name is None or dataset_fingerprint is None:
            return self._segment_with_progress(segmenter, split_name or "dataset", progress_every)
        key = hashlib.sha256(json.dumps({"version": CACHE_VERSION, "split": split_name, "dataset_sha256": dataset_fingerprint, "segmenter": segmenter_signature, "mode": "phobert_wseg"}, sort_keys=True).encode("utf-8")).hexdigest()
        path = cache_dir / f"{split_name}_{key}.json"
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("key") == key and isinstance(cached.get("texts"), list) and len(cached["texts"]) == len(self.records) and all(isinstance(text, str) for text in cached["texts"]):
                print(json.dumps({"stage": "preprocess_cache", "split": split_name, "status": "hit", "path": str(path), "rows": len(self.records)}, ensure_ascii=False), flush=True)
                return cached["texts"]
            raise ValueError("metadata or row count mismatch")
        except FileNotFoundError:
            print(json.dumps({"stage": "preprocess_cache", "split": split_name, "status": "miss", "path": str(path)}, ensure_ascii=False), flush=True)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            print(json.dumps({"stage": "preprocess_cache", "split": split_name, "status": "rebuild", "reason": type(exc).__name__}, ensure_ascii=False), flush=True)
        texts = self._segment_with_progress(segmenter, split_name, progress_every)
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps({"key": key, "version": CACHE_VERSION, "split": split_name, "dataset_sha256": dataset_fingerprint, "segmenter": segmenter_signature, "texts": texts}, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
        print(json.dumps({"stage": "preprocess_cache", "split": split_name, "status": "saved", "path": str(path), "rows": len(texts)}, ensure_ascii=False), flush=True)
        return texts

    def _segment_with_progress(self, segmenter, split_name: str, progress_every: int) -> list[str]:
        start = time.monotonic(); total = len(self.records); texts: list[str] = []
        for index, row in enumerate(self.records, 1):
            _, prepared = prepare_phobert_text(row["text"], segmenter)
            texts.append(prepared)
            if index == total or index % max(1, progress_every) == 0:
                elapsed = time.monotonic() - start; rate = index / max(elapsed, 1e-9); eta = (total - index) / max(rate, 1e-9)
                print(json.dumps({"stage": "preprocess_progress", "split": split_name, "completed": index, "total": total, "percent": round(100 * index / total, 2), "eta_seconds": round(eta, 1)}, ensure_ascii=False), flush=True)
        return texts

    def __len__(self): return len(self.records)

    def __getitem__(self, idx):
        row = self.records[idx]
        text = self.texts[idx]
        tok = self.tokenizer(text, truncation=True, max_length=self.max_length, padding="max_length", return_tensors="pt")
        aspect = torch.zeros(len(ASPECTS), dtype=torch.float32)
        sentiment = torch.full((len(ASPECTS),), -100, dtype=torch.long)
        for ann in row.get("annotations", []):
            ai = ASPECTS.index(ann["aspect"]); si = SENTIMENTS.index(ann["sentiment"])
            aspect[ai] = 1.0; sentiment[ai] = si
        return {
            "input_ids": tok["input_ids"].squeeze(0),
            "attention_mask": tok["attention_mask"].squeeze(0),
            "aspect_targets": aspect,
            "sentiment_targets": sentiment,
        }


def class_weights(records: list[dict], device):
    pos = np.zeros(len(ASPECTS), dtype=float)
    neg = np.zeros(len(ASPECTS), dtype=float)
    sent = np.zeros(len(SENTIMENTS), dtype=float)
    for row in records:
        present = {a["aspect"] for a in row.get("annotations", [])}
        for i, aspect in enumerate(ASPECTS):
            (pos if aspect in present else neg)[i] += 1
        for ann in row.get("annotations", []):
            sent[SENTIMENTS.index(ann["sentiment"])] += 1
    pos_weight = torch.tensor(np.divide(neg, np.maximum(pos, 1.0)), dtype=torch.float32, device=device)
    inv = sent.sum() / np.maximum(sent, 1.0)
    inv = inv / max(inv.mean(), 1e-9)
    sent_weight = torch.tensor(inv, dtype=torch.float32, device=device)
    if not torch.isfinite(pos_weight).all() or not torch.isfinite(sent_weight).all():
        raise ValueError(f"Non-finite class weights: pos={pos_weight.tolist()} sentiment={sent_weight.tolist()}")
    print(json.dumps({"aspect_pos_weight_min": float(pos_weight.min()), "aspect_pos_weight_max": float(pos_weight.max()), "sentiment_weight_min": float(sent_weight.min()), "sentiment_weight_max": float(sent_weight.max())}))
    return pos_weight, sent_weight


def prediction_payload(aspect_logits, sentiment_logits, thresholds):
    a_probs = torch.sigmoid(aspect_logits).cpu().numpy()
    s_probs = torch.softmax(sentiment_logits, dim=-1).cpu().numpy()
    payload = []
    for bi in range(a_probs.shape[0]):
        item = {"aspects": [], "aspect_scores": {}, "sentiment_by_aspect": {}, "sentiment_scores": {}}
        for ai, aspect in enumerate(ASPECTS):
            a_score = float(a_probs[bi, ai]); sent_idx = int(np.argmax(s_probs[bi, ai])); sent = SENTIMENTS[sent_idx]
            item["aspect_scores"][aspect] = a_score
            item["sentiment_by_aspect"][aspect] = sent
            item["sentiment_scores"][aspect] = {SENTIMENTS[j]: float(s_probs[bi, ai, j]) for j in range(len(SENTIMENTS))}
            if a_score >= thresholds.get(aspect, 0.5):
                item["aspects"].append({"aspect": aspect, "sentiment": sent, "aspect_score": a_score, "sentiment_score": float(s_probs[bi, ai, sent_idx])})
        item["status"] = "ok" if item["aspects"] else "no_aspect"
        payload.append(item)
    return payload


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_preflight_gate(report_path: Path, train: Path, dev: Path, backbone_name: str, max_length: int) -> None:
    """Fail closed before any pretrained model, dataset, or optimizer is opened."""
    if not report_path.exists():
        raise ValueError(f"preflight report missing: {report_path}")
    preflight = json.loads(report_path.read_text(encoding="utf-8"))
    expected_paths = {"train": str(train.resolve()), "dev": str(dev.resolve())}
    if preflight.get("overall_preflight") != "PASS" or preflight.get("dataset") != expected_paths:
        raise ValueError("preflight did not PASS for the requested Train/Dev paths; rerun nlp.training.preflight_transformer.")
    contract = preflight.get("training_contract")
    expected_contract = {
        "train_sha256": _file_sha256(train),
        "dev_sha256": _file_sha256(dev),
        "backbone_name": backbone_name,
        "max_length": max_length,
        "taxonomy_version": "absa-v1",
        "taxonomy": {"aspects": list(ASPECTS), "sentiments": list(SENTIMENTS)},
        "weighting_strategy": "raw_negative_positive_aspect__normalized_inverse_frequency_sentiment",
    }
    if not isinstance(contract, dict) or any(contract.get(key) != value for key, value in expected_contract.items()):
        raise ValueError("preflight training contract (dataset fingerprint, taxonomy, backbone, max length, or weighting) does not match; rerun nlp.training.preflight_transformer.")


def atomic_torch_save(value: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save(value, tmp)
    os.replace(tmp, path)


def rng_state() -> dict:
    state = {"python": random.getstate(), "numpy": np.random.get_state(), "torch": torch.get_rng_state()}
    if torch.cuda.is_available(): state["cuda"] = torch.cuda.get_rng_state_all()
    return state


def restore_rng_state(state: dict) -> None:
    random.setstate(state["python"]); np.random.set_state(state["numpy"]); torch.set_rng_state(state["torch"])
    if torch.cuda.is_available() and state.get("cuda") is not None: torch.cuda.set_rng_state_all(state["cuda"])


def deterministic_train_loader(dataset: Dataset, batch_size: int, seed: int, epoch: int) -> DataLoader:
    generator = torch.Generator(); generator.manual_seed(seed + epoch)
    return DataLoader(dataset, batch_size=batch_size, shuffle=True, generator=generator)


def resolve_cli_paths(args):
    """Freeze CLI paths before py_vncorenlp changes the process working directory."""
    for key in ("train", "dev", "out", "vncorenlp_dir", "resume", "cache_dir", "preflight_report"):
        value = getattr(args, key, None)
        if value is not None:
            setattr(args, key, Path(value).resolve())
    return args


def infer(model, loader, device, thresholds, *, aspect_pos_weight=None, sentiment_class_weight=None):
    model.eval(); preds = []; losses = []
    with torch.inference_mode():
        for batch in loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            out = model(**batch, aspect_pos_weight=aspect_pos_weight, sentiment_class_weight=sentiment_class_weight)
            if out.loss is not None: losses.append(float(out.loss.item()))
            preds.extend(prediction_payload(out.aspect_logits, out.sentiment_logits, thresholds))
    return preds, (sum(losses)/len(losses) if losses else 0.0)


def main():
    p = argparse.ArgumentParser(description="Train Vietnamese multi-task ABSA Transformer")
    p.add_argument("--config", type=Path, default=None, help="Optional JSON config; explicit CLI values override it")
    p.add_argument("--backbone", choices=BACKBONES, default=None)
    p.add_argument("--train", type=Path, default=ROOT/"nlp/data/gold/train.jsonl")
    p.add_argument("--dev", type=Path, default=ROOT/"nlp/data/gold/dev.jsonl")
    p.add_argument("--out", "--output-dir", dest="out", type=Path, default=None)
    p.add_argument("--vncorenlp-dir", type=Path, default=None)
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--max-length", type=int, default=256)
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--weight-decay", type=float, default=0.01)
    p.add_argument("--warmup-ratio", type=float, default=0.10)
    p.add_argument("--patience", type=int, default=2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="auto", help="auto, cpu, cuda, or a torch device such as cuda:0")
    p.add_argument("--resume", type=Path, default=None, help="Resume optimizer/model state from a last.pt checkpoint")
    p.add_argument("--save-every-steps", type=int, default=500, help="Atomically update resumable last.pt every N optimizer steps (0 disables periodic saves)")
    p.add_argument("--cache-dir", type=Path, default=ROOT / "model_artifacts" / "cache", help="Persistent segmented-text cache; Test is never cached by this trainer")
    p.add_argument("--progress-every", type=int, default=100, help="Emit structured preprocess progress every N rows")
    p.add_argument("--log-every-steps", type=int, default=50, help="Emit structured train progress every N steps")
    p.add_argument("--experimental", action="store_true", help="Record this run as non-scientific because its data is not human-verified gold.")
    p.add_argument("--preflight-report", type=Path, default=ROOT / "model_artifacts" / "preflight_transformer_report.json")
    args = p.parse_args()
    if args.config:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise SystemExit("--config must contain a JSON object")
        for key, value in config.items():
            if not hasattr(args, key):
                raise SystemExit(f"Unknown training config key: {key}")
            # argparse defaults are intentionally the documented defaults; only
            # fill settings where the caller did not pass a non-default option.
            if getattr(args, key) == p.get_default(key):
                setattr(args, key, value)
        for key in ("train", "dev", "out", "vncorenlp_dir", "resume", "cache_dir"):
            value = getattr(args, key)
            if isinstance(value, str):
                setattr(args, key, Path(value))
    if args.backbone is None:
        raise SystemExit("Specify --backbone phobert|bamibert (or set backbone in --config)")
    # py_vncorenlp may mutate cwd while its JVM starts; all file contracts need
    # stable absolute paths before that happens.
    args = resolve_cli_paths(args)
    # Full training is fail-closed: only a fresh PASS report for these exact
    # Train/Dev paths may unlock it.  The preflight command itself never reads
    # Test, so this guard cannot leak held-out labels into selection.
    try:
        validate_preflight_gate(args.preflight_report, args.train, args.dev, BACKBONES[args.backbone], args.max_length)
    except ValueError as exc:
        raise SystemExit(f"Full training blocked: {exc}") from exc
    seed_all(args.seed)
    try:
        from transformers import AutoTokenizer, get_linear_schedule_with_warmup  # type: ignore
    except ImportError as exc:
        raise SystemExit("Install requirements-train.txt before Transformer training") from exc
    train_rows, dev_rows = read_jsonl(args.train), read_jsonl(args.dev)
    if not train_rows or not dev_rows: raise SystemExit("Train/Dev gold data is empty")
    backbone_name = BACKBONES[args.backbone]
    segmenter = None
    if args.backbone == "phobert":
        if args.vncorenlp_dir is None:
            raise SystemExit("PhoBERT requires --vncorenlp-dir for project-consistent word segmentation")
        segmenter = VnCoreNLPSegmenter(args.vncorenlp_dir)
    tokenizer = AutoTokenizer.from_pretrained(backbone_name, use_fast=False)
    segmenter_signature = PHOBERT_PREPROCESSING_VERSION if segmenter else "raw"
    train_ds = ABSADataset(train_rows, tokenizer, args.max_length, segmenter, cache_dir=args.cache_dir, split_name="train", dataset_fingerprint=_file_sha256(args.train), segmenter_signature=segmenter_signature, progress_every=args.progress_every)
    dev_ds = ABSADataset(dev_rows, tokenizer, args.max_length, segmenter, cache_dir=args.cache_dir, split_name="dev", dataset_fingerprint=_file_sha256(args.dev), segmenter_signature=segmenter_signature, progress_every=args.progress_every)
    dev_loader = DataLoader(dev_ds, batch_size=args.batch_size, shuffle=False)
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
        if device.type == "cuda" and not torch.cuda.is_available():
            raise SystemExit(f"Requested {device}, but CUDA is unavailable")
    print(json.dumps({"stage": "training", "device": str(device), "cuda_available": torch.cuda.is_available(), "train_rows": len(train_rows), "dev_rows": len(dev_rows)}, ensure_ascii=False))
    model = MultiTaskABSA(backbone_name).to(device)
    pos_weight, sent_weight = class_weights(train_rows, device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    total_steps = max(1, ((len(train_ds) + args.batch_size - 1) // args.batch_size) * args.epochs)
    scheduler = get_linear_schedule_with_warmup(optimizer, int(total_steps*args.warmup_ratio), total_steps)
    out_dir = args.out or (ROOT / f"model_artifacts/{args.backbone}_absa_seed{args.seed}")
    out_dir.mkdir(parents=True, exist_ok=True)
    training_config = {
        "backbone_key": args.backbone,
        "backbone_name": backbone_name,
        "train": str(args.train.resolve()),
        "dev": str(args.dev.resolve()),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "max_length": args.max_length,
        "learning_rate": args.lr,
        "weight_decay": args.weight_decay,
        "warmup_ratio": args.warmup_ratio,
        "patience": args.patience,
        "seed": args.seed,
        "device": str(device),
        "gradient_clip_norm": 1.0,
        "weighting_strategy": WEIGHTING_STRATEGY,
        "dataset_fingerprints": {"train": _file_sha256(args.train), "dev": _file_sha256(args.dev)},
        "save_every_steps": args.save_every_steps,
        "preflight_report": str(args.preflight_report.resolve()),
    }
    (out_dir / "training_config.json").write_text(json.dumps(training_config, ensure_ascii=False, indent=2), encoding="utf-8")

    best = -1.0; best_epoch = 0; bad_epochs = 0; history = []; thresholds = {a:0.5 for a in ASPECTS}; start_epoch = 1; resume_batches_completed = 0; global_step = 0
    trainable_params = [param for param in model.parameters() if param.requires_grad]
    if args.resume:
        resume_path = args.resume / "last.pt" if args.resume.is_dir() else args.resume
        if not resume_path.exists():
            raise SystemExit(f"Resume checkpoint not found: {resume_path}")
        state = torch.load(resume_path, map_location=device, weights_only=False)
        saved_config = state.get("training_config", {})
        required = ("backbone_name", "max_length", "learning_rate", "weight_decay", "warmup_ratio", "batch_size", "dataset_fingerprints", "weighting_strategy")
        if any(saved_config.get(key) != training_config.get(key) for key in required):
            raise SystemExit("Resume checkpoint is incompatible with backbone/dataset/config/weighting; start a clean run instead")
        model.load_state_dict(state["model"]); optimizer.load_state_dict(state["optimizer"]); scheduler.load_state_dict(state["scheduler"])
        best = float(state.get("best", best)); best_epoch = int(state.get("best_epoch", 0)); bad_epochs = int(state.get("bad_epochs", 0)); history = list(state.get("history", [])); thresholds = dict(state.get("thresholds", thresholds)); start_epoch = int(state["epoch"]); resume_batches_completed = int(state.get("batches_completed", 0)); global_step = int(state.get("global_step", 0)); restore_rng_state(state["rng_state"])
        print(json.dumps({"stage":"resume","path":str(resume_path),"epoch":start_epoch,"batches_completed":resume_batches_completed,"global_step":global_step}, ensure_ascii=False), flush=True)
    for epoch in range(start_epoch, args.epochs+1):
        train_loader = deterministic_train_loader(train_ds, args.batch_size, args.seed, epoch)
        model.train(); losses=[]; max_gradient_norm=0.0; non_finite_gradient_count=0; skip_until = resume_batches_completed if epoch == start_epoch else 0
        epoch_started = time.monotonic()
        for batch_index, batch in enumerate(train_loader):
            if batch_index < skip_until: continue
            batch = {k:v.to(device) for k,v in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            out = model(**batch, aspect_pos_weight=pos_weight, sentiment_class_weight=sent_weight)
            finite = {"aspect_logits": out.aspect_logits, "sentiment_logits": out.sentiment_logits, "aspect_loss": out.aspect_loss, "sentiment_loss": out.sentiment_loss, "total_loss": out.loss}
            bad = [name for name, value in finite.items() if value is None or not torch.isfinite(value).all()]
            if bad:
                raise FloatingPointError(f"Non-finite values before backward at epoch={epoch} batch={batch_index}: {bad}")
            out.loss.backward()
            try:
                pre_clip_norm = float(torch.nn.utils.clip_grad_norm_(trainable_params, 1.0, error_if_nonfinite=True))
            except RuntimeError as exc:
                non_finite_gradient_count += 1
                raise FloatingPointError(f"Non-finite gradients at epoch={epoch} batch={batch_index}") from exc
            max_gradient_norm=max(max_gradient_norm,pre_clip_norm)
            optimizer.step(); scheduler.step(); global_step += 1; losses.append(float(out.loss.item()))
            if global_step % max(1, args.log_every_steps) == 0:
                completed = batch_index + 1
                elapsed = time.monotonic() - epoch_started
                rate = max(completed - skip_until, 1) / max(elapsed, 1e-9)
                eta = (len(train_loader) - completed) / max(rate, 1e-9)
                print(json.dumps({"stage":"train_progress","epoch":epoch,"epochs":args.epochs,"batch":completed,"batches":len(train_loader),"percent":round(100 * completed / len(train_loader),2),"global_step":global_step,"loss":losses[-1],"lr":scheduler.get_last_lr()[0],"eta_seconds":round(eta,1)}, ensure_ascii=False), flush=True)
            if args.save_every_steps > 0 and global_step % args.save_every_steps == 0:
                atomic_torch_save({"model":model.state_dict(),"optimizer":optimizer.state_dict(),"scheduler":scheduler.state_dict(),"epoch":epoch,"batches_completed":batch_index + 1,"global_step":global_step,"best":best,"best_epoch":best_epoch,"bad_epochs":bad_epochs,"history":history,"thresholds":thresholds,"max_gradient_norm":max_gradient_norm,"non_finite_gradient_count":non_finite_gradient_count,"training_config":training_config,"rng_state":rng_state()}, out_dir / "last.pt")
        raw_dev, dev_loss = infer(model, dev_loader, device, {a:0.5 for a in ASPECTS}, aspect_pos_weight=pos_weight, sentiment_class_weight=sent_weight)
        thresholds, threshold_curves = tune_aspect_thresholds(dev_rows, raw_dev)
        dev_preds, _ = infer(model, dev_loader, device, thresholds, aspect_pos_weight=pos_weight, sentiment_class_weight=sent_weight)
        metrics = evaluate_records(dev_rows, dev_preds)
        score = metrics["pair_macro_f1_strict_union"]
        history.append({"epoch":epoch,"train_loss":sum(losses)/max(1,len(losses)),"dev_loss":dev_loss,"dev_pair_macro_f1":metrics["pair_macro_f1"],"dev_pair_macro_f1_strict_union":score,"max_gradient_norm_pre_clip":max_gradient_norm,"non_finite_gradient_count":non_finite_gradient_count})
        print(json.dumps(history[-1], ensure_ascii=False))
        if score > best + 1e-6:
            best = score; best_epoch=epoch; bad_epochs=0
            torch.save(model.state_dict(), out_dir/"model.pt")
            tokenizer.save_pretrained(out_dir/"tokenizer")
            model.encoder.config.save_pretrained(out_dir/"encoder_config")
            (out_dir/"thresholds.json").write_text(json.dumps(thresholds,indent=2),encoding="utf-8")
            (out_dir/"dev_threshold_curves.json").write_text(json.dumps(threshold_curves,ensure_ascii=False,indent=2),encoding="utf-8")
            (out_dir/"dev_metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
        else:
            bad_epochs += 1
        atomic_torch_save({"model":model.state_dict(),"optimizer":optimizer.state_dict(),"scheduler":scheduler.state_dict(),"epoch":epoch + 1,"batches_completed":0,"global_step":global_step,"best":best,"best_epoch":best_epoch,"bad_epochs":bad_epochs,"history":history,"thresholds":thresholds,"max_gradient_norm":max_gradient_norm,"non_finite_gradient_count":non_finite_gradient_count,"training_config":training_config,"rng_state":rng_state()}, out_dir / "last.pt")
        resume_batches_completed = 0
        if bad_epochs >= args.patience:
            break
    manifest = {
        "backbone_key": args.backbone,
        "backbone_name": backbone_name,
        "seed": args.seed,
        "max_length": args.max_length,
        "primary_metric": "dev_pair_macro_f1_strict_union",
        "best_dev_pair_macro_f1_strict_union": best,
        "best_epoch": best_epoch,
        "selection_gate": "strict-union Pair Macro-F1 on Dev; legacy gold-active Pair Macro-F1 remains reported as a diagnostic",
        "history": history,
        "test_was_used": False,
        "scientific_final": False,
        "experimental_only": bool(args.experimental),
        "data_protocol": "experimental_non_scientific" if args.experimental else "gold_candidate_requires_final_audit",
        "offline_runtime_files": ["model.pt", "last.pt", "tokenizer/", "encoder_config/", "thresholds.json", "training_config.json", "dev_metrics.json"],
        "device": str(device),
        "training_config_file": "training_config.json",
        "taxonomy": {"aspects": list(ASPECTS), "sentiments": list(SENTIMENTS)},
    }
    (out_dir/"training_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Saved best Dev checkpoint to {out_dir}")


if __name__ == "__main__":
    main()
