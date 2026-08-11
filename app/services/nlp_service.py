from __future__ import annotations

import re
import logging
from pathlib import Path
from threading import Lock

import joblib

from app.config import ROOT, settings
from nlp.preprocessing.text import normalize_text

_LOCK = Lock()
_INSTANCE = None
_ALPHA_RE = re.compile(r"[A-Za-zÀ-ỹĐđ]+", re.UNICODE)
logger = logging.getLogger(__name__)


def is_meaningful_feedback(text: str) -> bool:
    tokens = _ALPHA_RE.findall(normalize_text(text))
    if len(tokens) >= 3:
        return True
    # Permit short but semantically strong Vietnamese reviews.
    strong = {"đắt", "rẻ", "tệ", "đẹp", "hỏng", "chậm", "nhanh", "móp", "rách"}
    return any(t.casefold() in strong for t in tokens)


class AnalyzerRegistry:
    def __init__(self):
        self.primary = None
        self.primary_name = "unavailable"
        self.backend = settings.nlp_backend
        artifact = ROOT / "model_artifacts" / "baseline_absa_v0" / "baseline.joblib"
        if self.backend == "transformer":
            if not settings.transformer_artifact:
                raise RuntimeError("NLP_BACKEND=transformer requires TRANSFORMER_ARTIFACT; no rule/demo fallback is permitted")
            path = Path(settings.transformer_artifact)
            if not path.exists():
                raise RuntimeError(f"Configured Transformer artifact does not exist: {path}")
            try:
                from nlp.inference.transformer_analyzer import TransformerAnalyzer
                self.primary = TransformerAnalyzer(
                    path,
                    vncorenlp_dir=settings.vncorenlp_dir or None,
                    allow_experimental=settings.allow_experimental_transformer,
                    device=settings.transformer_device,
                )
                self.primary_name = "transformer"
                logger.info(
                    "NLP runtime initialized backend=transformer artifact=%s experimental=%s scientific_final=%s device=%s preprocessing=%s",
                    self.primary.artifact_dir,
                    self.primary.manifest["experimental_only"],
                    self.primary.manifest["scientific_final"],
                    self.primary.device,
                    self.primary.preprocessing_version,
                )
            except Exception as exc:
                raise RuntimeError(f"Cannot load configured Transformer artifact: {type(exc).__name__}: {exc}") from exc
        elif self.backend in {"demo", "baseline"}:
            if not artifact.exists():
                raise RuntimeError(f"{self.backend} runtime requires bundled artifact: {artifact}")
            self.primary = joblib.load(artifact)
            self.primary_name = "demo_baseline" if self.backend == "demo" else "baseline"
        else:
            raise RuntimeError("NLP_BACKEND must be one of: transformer, baseline, demo")

    def analyze(self, text: str) -> dict:
        if self.backend == "transformer":
            # The Transformer owns its shared raw-text preprocessing path.
            # Do not pass keyword extraction or the demo meaningfulness guard.
            return self.primary.analyze(text)
        clean = normalize_text(text)
        if self.backend == "demo" and not is_meaningful_feedback(clean):
            return {"text": clean, "status": "no_aspect", "aspects": [], "model_version": "meaningfulness-gate-v1", "backend": "meaningfulness_gate"}
        result = self.primary.analyze(clean)
        # Never modify Transformer predictions with deterministic semantics.
        # The demo-only guard remains isolated for UX fixtures and test support.
        if self.backend == "demo":
            from nlp.inference.demo_semantic_guard import apply_demo_semantic_guard
            result = apply_demo_semantic_guard(result, clean)
        return result


def get_analyzer() -> AnalyzerRegistry:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = AnalyzerRegistry()
    return _INSTANCE


def reset_analyzer_for_tests() -> None:
    global _INSTANCE
    _INSTANCE = None
