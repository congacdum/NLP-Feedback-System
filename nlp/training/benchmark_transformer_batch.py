"""Bounded CUDA batch-size benchmark; never reads Dev/Test or saves an artifact."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import statistics
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Subset

from nlp.models.multitask_transformer import MultiTaskABSA
from nlp.preprocessing.segmenter import PHOBERT_PREPROCESSING_VERSION, VnCoreNLPSegmenter
from nlp.training.train_transformer import ABSADataset, BACKBONES, ROOT, _file_sha256, class_weights, read_jsonl, seed_all


def process_cpu_seconds() -> float | None:
    """Return this process' CPU seconds without an external dependency."""
    if os.name != "nt":
        return time.process_time()
    class FileTime(ctypes.Structure):
        _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]
    creation = FileTime(); exit_time = FileTime(); kernel = FileTime(); user = FileTime()
    if not ctypes.windll.kernel32.GetProcessTimes(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(kernel), ctypes.byref(user)):
        return time.process_time()
    def seconds(value: FileTime) -> float:
        return ((int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)) / 10_000_000
    return seconds(kernel) + seconds(user)


class GpuSampler:
    """Low-overhead GPU telemetry for a bounded benchmark only."""
    def __init__(self) -> None:
        self.samples: list[dict[str, float]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._last_cpu_seconds = process_cpu_seconds()
        self._last_cpu_wall = time.perf_counter()

    def _sample(self) -> None:
        while not self._stop.is_set():
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=3, check=True,
                )
                fields = result.stdout.strip().splitlines()[0].split(",")
                sample = {"gpu_utilization": float(fields[0]), "memory_used_mib": float(fields[1])}
                cpu_seconds, cpu_wall = process_cpu_seconds(), time.perf_counter()
                if cpu_seconds is not None and self._last_cpu_seconds is not None:
                    sample["process_cpu_percent"] = 100 * (cpu_seconds - self._last_cpu_seconds) / max(cpu_wall - self._last_cpu_wall, 1e-9)
                self._last_cpu_seconds, self._last_cpu_wall = cpu_seconds, cpu_wall
                self.samples.append(sample)
            except (OSError, subprocess.SubprocessError, IndexError, ValueError):
                pass
            self._stop.wait(0.2)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> dict[str, float | None]:
        self._stop.set(); self._thread.join(timeout=3)
        if not self.samples:
            return {"gpu_utilization_average": None, "gpu_utilization_peak": None, "gpu_memory_used_peak_mib": None, "process_cpu_percent_average": None, "process_cpu_percent_peak": None}
        return {
            "gpu_utilization_average": round(statistics.fmean(s["gpu_utilization"] for s in self.samples), 2),
            "gpu_utilization_peak": max(s["gpu_utilization"] for s in self.samples),
            "gpu_memory_used_peak_mib": max(s["memory_used_mib"] for s in self.samples),
            "process_cpu_percent_average": round(statistics.fmean(s["process_cpu_percent"] for s in self.samples if "process_cpu_percent" in s), 2) if any("process_cpu_percent" in s for s in self.samples) else None,
            "process_cpu_percent_peak": max(s["process_cpu_percent"] for s in self.samples if "process_cpu_percent" in s) if any("process_cpu_percent" in s for s in self.samples) else None,
        }


def make_loader(dataset, batch_size: int, steps: int, num_workers: int) -> DataLoader:
    return DataLoader(
        Subset(dataset, list(range(min(len(dataset), batch_size * steps)))),
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
        persistent_workers=num_workers > 0,
    )


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def run(batch_size: int, num_workers: int, steps: int, args, rows, tokenizer, segmenter) -> dict:
    device = torch.device("cuda")
    torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats(device)
    dataset = ABSADataset(rows, tokenizer, args.max_length, segmenter, cache_dir=args.cache_dir, split_name="train", dataset_fingerprint=_file_sha256(args.train), segmenter_signature=PHOBERT_PREPROCESSING_VERSION, progress_every=args.progress_every)
    loader = make_loader(dataset, batch_size, steps, num_workers)
    model = MultiTaskABSA(BACKBONES["phobert"]).to(device); pw, sw = class_weights(rows, device); opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay); params=[p for p in model.parameters() if p.requires_grad]
    from transformers import get_linear_schedule_with_warmup
    scheduler = get_linear_schedule_with_warmup(opt, int(steps * args.warmup_ratio), steps)
    # Do not include loader startup/model setup in optimizer-step timing.
    sampler = GpuSampler(); sampler.start(); step_times=[]; stages={name: [] for name in ("data_wait", "host_to_device", "forward_loss", "backward", "gradient_clip", "optimizer_step", "scheduler_step")}; start=time.perf_counter(); done=0
    try:
        iterator = iter(loader)
        while done < steps:
            if done >= steps: break
            step_start=time.perf_counter()
            wait_start=time.perf_counter(); batch=next(iterator); stages["data_wait"].append(time.perf_counter()-wait_start)
            transfer_start=time.perf_counter(); batch={k:v.to(device, non_blocking=True) for k,v in batch.items()}; stages["host_to_device"].append(time.perf_counter()-transfer_start)
            opt.zero_grad(set_to_none=True); forward_start=time.perf_counter(); out=model(**batch,aspect_pos_weight=pw,sentiment_class_weight=sw); stages["forward_loss"].append(time.perf_counter()-forward_start)
            if not all(torch.isfinite(x).all() for x in (out.aspect_logits,out.sentiment_logits,out.aspect_loss,out.sentiment_loss,out.loss)): raise FloatingPointError("non-finite logits or loss")
            backward_start=time.perf_counter(); out.loss.backward(); stages["backward"].append(time.perf_counter()-backward_start)
            clip_start=time.perf_counter(); torch.nn.utils.clip_grad_norm_(params,1.0,error_if_nonfinite=True); stages["gradient_clip"].append(time.perf_counter()-clip_start)
            optimizer_start=time.perf_counter(); opt.step(); stages["optimizer_step"].append(time.perf_counter()-optimizer_start)
            scheduler_start=time.perf_counter(); scheduler.step(); stages["scheduler_step"].append(time.perf_counter()-scheduler_start); done+=1
            step_times.append(time.perf_counter()-step_start)
        elapsed=time.perf_counter()-start
        telemetry = sampler.stop()
        return {"batch_size":batch_size,"num_workers":num_workers,"steps":done,"status":"PASS","peak_vram_bytes":int(torch.cuda.max_memory_allocated(device)),"steps_per_second":done/max(elapsed,1e-9),"samples_per_second":done*batch_size/max(elapsed,1e-9),"average_step_seconds":elapsed/max(done,1),"median_step_seconds":statistics.median(step_times) if step_times else None,"p95_step_seconds":sorted(step_times)[max(0, int(len(step_times)*.95)-1)] if step_times else None,"stage_mean_seconds":{name: _mean(values) for name, values in stages.items()},"gpu":torch.cuda.get_device_name(0),**telemetry}
    except torch.cuda.OutOfMemoryError as exc:
        return {"batch_size":batch_size,"steps":done,"status":"OOM","error":str(exc),"peak_vram_bytes":int(torch.cuda.max_memory_allocated(device))}
    finally:
        if sampler._thread.is_alive(): sampler.stop()
        del model; torch.cuda.empty_cache()


def main() -> None:
    p=argparse.ArgumentParser(description="Bounded PhoBERT batch benchmark; Train only, no artifact/evaluation.")
    p.add_argument("--train",type=Path,default=ROOT/"nlp/data/experimental/train.jsonl"); p.add_argument("--vncorenlp-dir",type=Path,required=True); p.add_argument("--cache-dir",type=Path,default=ROOT/"model_artifacts/cache"); p.add_argument("--max-length",type=int,default=256); p.add_argument("--lr",type=float,default=2e-5); p.add_argument("--weight-decay",type=float,default=.01); p.add_argument("--warmup-ratio",type=float,default=.1); p.add_argument("--steps",type=int,default=100); p.add_argument("--batch-size",type=int,default=8); p.add_argument("--num-workers",type=str,default="0,2,4",help="Comma-separated Windows worker candidates for bounded benchmark"); p.add_argument("--progress-every",type=int,default=100); p.add_argument("--output",type=Path,default=ROOT/"model_artifacts/batch_benchmark_phobert.json")
    args=p.parse_args()
    if not torch.cuda.is_available(): raise SystemExit("CUDA is required")
    seed_all(42); from transformers import AutoTokenizer
    rows=read_jsonl(args.train); tokenizer=AutoTokenizer.from_pretrained(BACKBONES["phobert"],use_fast=False); segmenter=VnCoreNLPSegmenter(args.vncorenlp_dir)
    workers = [int(value.strip()) for value in args.num_workers.split(",") if value.strip()]
    if not workers or any(value < 0 for value in workers): raise SystemExit("--num-workers must contain non-negative integers")
    results=[run(args.batch_size, workers_count, args.steps, args, rows, tokenizer, segmenter) for workers_count in workers]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    output = {"train":str(args.train.resolve()),"test_read":False,"challenge_read":False,"full_training_launched":False,"results":results}
    print(json.dumps(results,ensure_ascii=False,indent=2))
    # A unique sibling avoids a stale antivirus/indexer handle on a predictable
    # ``.tmp`` filename; replacement still makes the completed report atomic.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent, suffix=".tmp", prefix=f".{args.output.name}.", delete=False) as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
        tmp_name = handle.name
    os.replace(tmp_name, args.output)

if __name__=="__main__": main()
