"""Optional local Hugging Face inference adapters.

No network download or model execution occurs during import/startup.
Weights must be provisioned by an operator in a local directory. All
outputs are advisory and based exclusively on caller-supplied inputs.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    values: list[float] = Field(min_length=32, max_length=4096)
    horizon: int = Field(default=12, ge=1, le=96)
    model: Literal["granite-ttm", "chronos"] = "granite-ttm"
    sampling_interval_minutes: int = Field(default=15, ge=1, le=1440)


class KnowledgeRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    excerpts: list[str] = Field(min_length=1, max_length=12)


MODEL_IDS = {
    "granite-ttm": "ibm-granite/granite-timeseries-ttm-r2",
    "chronos": "amazon/chronos-t5-small",
    "qwen": "Qwen/Qwen3-4B-Instruct-2507",
    "bge-m3": "BAAI/bge-m3",
}


def model_status() -> dict:
    base = os.getenv("BUILDOPT_HF_MODELS_DIR", "")
    paths = {}
    for name in MODEL_IDS:
        folder = Path(base) / name if base else None
        paths[name] = {
            "model_id": MODEL_IDS[name],
            "installed": bool(folder and folder.is_dir() and any(folder.iterdir())),
        }
    return {
        "mode": "LOCAL_OPT_IN",
        "read_only": True,
        "automatic_downloads": False,
        "models": paths,
        "note": "Presence does not establish inference compatibility or readiness.",
    }


def validate_forecast(req: ForecastRequest) -> dict:
    from math import isfinite
    if not all(isfinite(v) for v in req.values):
        raise ValueError("All samples must be finite")
    return {
        "source": "USER_SUPPLIED",
        "verified": False,
        "model": req.model,
        "sample_count": len(req.values),
        "horizon": req.horizon,
        "status": "MODEL_NOT_PROVISIONED",
        "predictions": None,
        "note": "Install and validate pinned model weights locally before enabling inference. No placeholder predictions returned.",
        "mode": "READ_ONLY",
    }


def knowledge_review(req: KnowledgeRequest) -> dict:
    return {
        "source": "USER_SUPPLIED",
        "verified": False,
        "status": "MODEL_NOT_PROVISIONED",
        "answer": None,
        "excerpts_received": len(req.excerpts),
        "note": "No language-model answer is fabricated without a locally validated model and retrieved evidence.",
        "mode": "READ_ONLY",
    }
