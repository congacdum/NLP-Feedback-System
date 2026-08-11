from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import torch

from nlp.models.multitask_transformer import MultiTaskABSA
from nlp.preprocessing.segmenter import PHOBERT_PREPROCESSING_VERSION, VnCoreNLPSegmenter, prepare_phobert_text
from nlp.schema import ASPECTS, SENTIMENTS

logger = logging.getLogger(__name__)
_REQUIRED_RUNTIME_FILES = ("model.pt", "thresholds.json", "training_manifest.json", "training_config.json")
_BACKBONES = {"phobert": "vinai/phobert-base-v2", "bamibert": "Qualcomm-AI-Research/BamiBERT"}


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Frozen Transformer artifact has unreadable {label}: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Frozen Transformer artifact {label} must be a JSON object")
    return value


def validate_runtime_artifact(artifact_dir: Path, *, allow_experimental: bool) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    """Validate local runtime metadata before loading any model state.

    A malformed artifact is a configuration error, not an excuse to fall back
    to a demo/baseline analyzer.  Validation deliberately contains no dataset
    or evaluator imports, so Test/Challenge cannot be read from this path.
    """
    missing = [name for name in _REQUIRED_RUNTIME_FILES if not (artifact_dir / name).is_file()]
    if missing:
        raise RuntimeError(f"Frozen Transformer artifact is missing required file(s): {', '.join(missing)}")
    if not (artifact_dir / "tokenizer").is_dir() or not (artifact_dir / "encoder_config" / "config.json").is_file():
        raise RuntimeError("Frozen Transformer artifact is missing local tokenizer or encoder_config/config.json")

    manifest = _load_json(artifact_dir / "training_manifest.json", "training_manifest.json")
    training_config = _load_json(artifact_dir / "training_config.json", "training_config.json")
    thresholds_raw = _load_json(artifact_dir / "thresholds.json", "thresholds.json")
    required_manifest = ("backbone_key", "backbone_name", "max_length", "taxonomy", "experimental_only", "scientific_final")
    missing_manifest = [key for key in required_manifest if key not in manifest]
    if missing_manifest:
        raise RuntimeError(f"Frozen Transformer manifest is missing: {', '.join(missing_manifest)}")
    backbone_key = manifest["backbone_key"]
    if backbone_key not in _BACKBONES or manifest["backbone_name"] != _BACKBONES[backbone_key]:
        raise RuntimeError("Frozen Transformer manifest backbone is unsupported or inconsistent")
    if not isinstance(manifest["max_length"], int) or manifest["max_length"] <= 0:
        raise RuntimeError("Frozen Transformer manifest max_length must be a positive integer")
    taxonomy = manifest["taxonomy"]
    if not isinstance(taxonomy, dict) or tuple(taxonomy.get("aspects", ())) != ASPECTS or tuple(taxonomy.get("sentiments", ())) != SENTIMENTS:
        raise RuntimeError("Frozen Transformer manifest taxonomy does not match the runtime schema")
    if not isinstance(manifest["experimental_only"], bool) or not isinstance(manifest["scientific_final"], bool):
        raise RuntimeError("Frozen Transformer manifest experimental/scientific flags must be boolean")
    if manifest["experimental_only"] and not allow_experimental:
        raise RuntimeError("Experimental Transformer artifact requires ALLOW_EXPERIMENTAL_TRANSFORMER=true")
    if training_config.get("backbone_name") != manifest["backbone_name"] or training_config.get("max_length") != manifest["max_length"]:
        raise RuntimeError("Frozen Transformer training_config does not match manifest backbone/max_length")
    if set(thresholds_raw) != set(ASPECTS):
        raise RuntimeError("Frozen Transformer thresholds must contain exactly the frozen aspect schema")
    try:
        thresholds = {aspect: float(thresholds_raw[aspect]) for aspect in ASPECTS}
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Frozen Transformer thresholds must be numeric") from exc
    if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in thresholds.values()):
        raise RuntimeError("Frozen Transformer thresholds must be finite values in [0, 1]")
    return manifest, training_config, thresholds


class TransformerAnalyzer:
    """Load a frozen project Transformer checkpoint for runtime inference.

    Long feedback is evaluated with overlapping tokenizer windows instead of
    silently truncating the tail. Aspect probabilities are max-pooled across
    windows. Sentiment probabilities are aspect-score-weighted; if separate
    confident windows express positive and negative sentiment for the same
    aspect, the runtime aggregate is ``mixed``.

    The supplied ZIP does not fabricate final Transformer weights: this loader
    becomes active only when a scientifically trained artifact is configured.
    """

    def __init__(self, artifact_dir: str | Path, *, vncorenlp_dir: str | Path | None = None, allow_experimental: bool = False, device: str = "auto"):
        self.artifact_dir = Path(artifact_dir).expanduser().resolve()
        if not self.artifact_dir.is_dir():
            raise RuntimeError(f"Configured Transformer artifact does not exist: {self.artifact_dir}")
        manifest, training_config, thresholds = validate_runtime_artifact(self.artifact_dir, allow_experimental=allow_experimental)
        try:
            from transformers import AutoTokenizer  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Transformer runtime requires requirements-train.txt") from exc
        self.manifest = manifest
        self.training_config = training_config
        self.thresholds = thresholds
        self.preprocessing_version = PHOBERT_PREPROCESSING_VERSION if manifest["backbone_key"] == "phobert" else "bamibert_normalize_raw_v1"
        tokenizer_dir = self.artifact_dir / "tokenizer"
        config_dir = self.artifact_dir / "encoder_config"
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir, use_fast=False, local_files_only=True)
        self.model = MultiTaskABSA(manifest["backbone_name"], encoder_config_dir=str(config_dir))
        self.model.load_state_dict(torch.load(self.artifact_dir / "model.pt", map_location="cpu", weights_only=True))
        self.device = self._resolve_device(device)
        self.model.to(self.device)
        self.model.eval()
        self.segmenter = None
        if manifest["backbone_key"] == "phobert":
            if vncorenlp_dir is None:
                raise RuntimeError("PhoBERT artifact requires a VnCoreNLP directory at runtime")
            self.segmenter = VnCoreNLPSegmenter(vncorenlp_dir)
        self.model_version = self.artifact_dir.name
        self.max_length = int(manifest["max_length"])

    @staticmethod
    def _resolve_device(requested: str) -> torch.device:
        requested = requested.strip().casefold()
        if requested == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if requested == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("TRANSFORMER_DEVICE=cuda was requested but CUDA is unavailable")
        if requested not in {"cpu", "cuda"}:
            raise RuntimeError("TRANSFORMER_DEVICE must be one of: auto, cpu, cuda")
        return torch.device(requested)

    def debug_preprocess(self, text: str) -> dict[str, str]:
        if self.segmenter is not None:
            normalized, segmented = prepare_phobert_text(text, self.segmenter)
        else:
            from nlp.preprocessing.text import normalize_text
            normalized = normalize_text(text)
            segmented = normalized
        return {
            "raw_text": text,
            "normalized_text": normalized,
            "segmented_text": segmented,
            "preprocessing_version": self.preprocessing_version,
        }

    def _encode_windows(self, text: str) -> dict[str, torch.Tensor]:
        # Overlap helps preserve meaning around window boundaries. Padding is
        # applied only inside this one inference call.
        if not getattr(self.tokenizer, "is_fast", False):
            # ``PhobertTokenizer`` is a slow tokenizer.  Unlike fast
            # tokenizers, its ``return_overflowing_tokens`` API returns one
            # truncated sequence plus a flat overflow list, rather than a
            # batch of windows.  Materialize the documented overlapping
            # windows ourselves so long runtime feedback is not silently
            # truncated.  This preserves the same segmented text, tokenizer,
            # max length and aggregation contract as the fast-tokenizer path.
            raw = self.tokenizer(text, add_special_tokens=False, truncation=False)
            token_ids = list(raw["input_ids"])
            special_tokens = int(self.tokenizer.num_special_tokens_to_add(pair=False))
            payload_size = self.max_length - special_tokens
            if payload_size <= 0:
                raise RuntimeError("Transformer max_length is too small for tokenizer special tokens")
            stride = min(48, max(0, self.max_length // 4), max(0, payload_size - 1))
            step = max(1, payload_size - stride)
            windows = []
            start = 0
            while True:
                window_ids = token_ids[start:start + payload_size]
                prepared = self.tokenizer.prepare_for_model(
                    window_ids,
                    add_special_tokens=True,
                    padding="max_length",
                    max_length=self.max_length,
                    truncation=True,
                    return_attention_mask=True,
                )
                windows.append(prepared)
                if start + payload_size >= len(token_ids):
                    break
                start += step
            return {
                "input_ids": torch.tensor([window["input_ids"] for window in windows], dtype=torch.long),
                "attention_mask": torch.tensor([window["attention_mask"] for window in windows], dtype=torch.long),
            }
        encoded = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            stride=min(48, max(0, self.max_length // 4)),
            return_overflowing_tokens=True,
            padding=True,
            return_tensors="pt",
        )
        return {"input_ids": encoded["input_ids"], "attention_mask": encoded["attention_mask"]}

    def analyze(self, text: str) -> dict:
        prepared = self.debug_preprocess(text)
        tok = self._encode_windows(prepared["segmented_text"])
        tok = {key: value.to(self.device) for key, value in tok.items()}
        with torch.inference_mode():
            out = self.model(tok["input_ids"], tok["attention_mask"])
            a_windows = torch.sigmoid(out.aspect_logits)  # windows × aspects
            s_windows = torch.softmax(out.sentiment_logits, dim=-1)  # windows × aspects × sentiments

        aspects = []
        aspect_scores = {}
        sentiment_by_aspect = {}
        sentiment_scores = {}
        for ai, aspect in enumerate(ASPECTS):
            threshold = float(self.thresholds.get(aspect, 0.5))
            per_window_a = a_windows[:, ai]
            a_score = float(torch.max(per_window_a))
            weights = per_window_a.clamp_min(1e-6)
            weighted = (s_windows[:, ai, :] * weights[:, None]).sum(dim=0) / weights.sum()
            si = int(torch.argmax(weighted))
            sent = SENTIMENTS[si]

            # Cross-window conflict is real evidence for the project-level MIXED
            # label even when each individual chunk contains only one polarity.
            active = torch.where(per_window_a >= threshold)[0]
            active_labels = set()
            for wi in active.tolist():
                local_idx = int(torch.argmax(s_windows[wi, ai]))
                local_score = float(torch.max(s_windows[wi, ai]))
                if local_score >= 0.50:
                    active_labels.add(SENTIMENTS[local_idx])
            if "positive" in active_labels and "negative" in active_labels:
                sent = "mixed"
                si = SENTIMENTS.index("mixed")

            aspect_scores[aspect] = a_score
            sentiment_by_aspect[aspect] = sent
            sentiment_scores[aspect] = {SENTIMENTS[j]: float(weighted[j]) for j in range(len(SENTIMENTS))}
            if a_score >= threshold:
                s_score = float(weighted[si]) if sent != "mixed" or weighted[si] > 0 else max(
                    float(weighted[SENTIMENTS.index("positive")]),
                    float(weighted[SENTIMENTS.index("negative")]),
                )
                aspects.append({
                    "aspect": aspect,
                    "sentiment": sent,
                    "aspect_score": a_score,
                    "sentiment_score": s_score,
                })
        result = {
            "text": prepared["normalized_text"],
            "status": "ok" if aspects else "no_aspect",
            "aspects": aspects,
            "aspect_scores": aspect_scores,
            "sentiment_by_aspect": sentiment_by_aspect,
            "sentiment_scores": sentiment_scores,
            "model_version": self.model_version,
            "backend": "transformer",
            "windows_used": int(tok["input_ids"].shape[0]),
        }
        logger.info(
            "Transformer analysis complete backend=transformer artifact=%s aspects=%s windows=%s",
            self.model_version,
            [item["aspect"] for item in aspects],
            result["windows_used"],
        )
        return result
