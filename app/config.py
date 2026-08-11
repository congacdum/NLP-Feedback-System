from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def env_flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "NLP Feedback System")
    secret_key: str = os.getenv("APP_SECRET", "change-this-in-production-demo-secret")
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'app.db'}")
    # ``transformer`` is strict scientific runtime: no rules or demo guard can
    # execute in that path. ``demo`` is intentionally visibly non-scientific.
    nlp_backend: str = os.getenv("NLP_BACKEND", "demo").strip().casefold()
    transformer_artifact: str = os.getenv("TRANSFORMER_ARTIFACT", "")
    # Experimental checkpoints are intentionally opt-in.  They are useful for
    # runtime integration work but must never be mistaken for a scientific-final
    # model simply because NLP_BACKEND is set to transformer.
    allow_experimental_transformer: bool = env_flag("ALLOW_EXPERIMENTAL_TRANSFORMER", False)
    transformer_device: str = os.getenv("TRANSFORMER_DEVICE", "auto").strip().casefold()
    evaluation_artifact: str = os.getenv("EVALUATION_ARTIFACT", "")
    vncorenlp_dir: str = os.getenv("VNCORENLP_DIR", "")
    rasa_url: str = os.getenv("RASA_URL", "http://rasa:5005")
    product_hf_base: str = os.getenv(
        "PRODUCT_HF_BASE",
        "https://huggingface.co/datasets/trucmtnguyen/multimodal-product-reviews-lazada/resolve/main/",
    )
    dev_demo_catalog: bool = env_flag("DEV_DEMO_CATALOG", False)
    cookie_name: str = "nlp_feedback_session"


settings = Settings()
