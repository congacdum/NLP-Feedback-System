from __future__ import annotations

import os
from pathlib import Path

from nlp.preprocessing.text import normalize_text


PHOBERT_PREPROCESSING_VERSION = "phobert_normalize_vncorenlp_wseg_v1"


def prepare_phobert_text(text: str, segmenter: "VnCoreNLPSegmenter") -> tuple[str, str]:
    """Return the exact normalized and word-segmented PhoBERT input.

    Training and runtime both call this function.  Keeping the normalized text
    alongside the segmented string makes contract checks possible without
    letting keyword extraction or UI formatting alter Transformer input.
    """
    normalized = normalize_text(text)
    return normalized, segmenter(normalized)


class VnCoreNLPSegmenter:
    """Thin optional wrapper around py_vncorenlp for PhoBERT preprocessing.

    VnCoreNLP models are intentionally not bundled in this repository. Training
    users must install ``py_vncorenlp`` and point ``save_dir`` to their local
    VnCoreNLP model directory. BamiBERT does not use this adapter.
    """

    def __init__(self, save_dir: str | Path):
        try:
            import py_vncorenlp  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional training dependency
            raise RuntimeError(
                "PhoBERT training requires py_vncorenlp. Install requirements-train.txt."
            ) from exc
        # py_vncorenlp changes its current working directory before setting
        # its classpath.  A relative path therefore becomes duplicated on
        # Windows (``vendor/.../vendor/...``) and the JAR cannot be loaded.
        # Restore it afterwards so an NLP load cannot alter application paths.
        runtime_dir = Path(save_dir).absolute()
        prior_cwd = os.getcwd()
        try:
            self._client = py_vncorenlp.VnCoreNLP(annotators=["wseg"], save_dir=str(runtime_dir))
        except Exception as exc:
            raise RuntimeError(
                f"Cannot initialize local VnCoreNLP from {runtime_dir}. "
                "Set JAVA_HOME and point VNCORENLP_DIR to a complete local resource directory. "
                "On Windows, pyjnius may require an ASCII-only VNCORENLP_DIR path."
            ) from exc
        finally:
            os.chdir(prior_cwd)

    def __call__(self, text: str) -> str:
        segmented = self._client.word_segment(text)
        return " ".join(segmented)
