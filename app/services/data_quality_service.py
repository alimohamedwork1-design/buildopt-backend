"""Data provenance and freshness classification for read-only telemetry.

The classification is intentionally conservative: absent timestamps or invalid
values never become LIVE. Consumers must not infer sensor values from this status.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Optional

from pydantic import BaseModel, Field


class DataQualityState(str, Enum):
    LIVE = "LIVE"
    STALE = "STALE"
    NO_DATA = "NO_DATA"
    DEMO = "DEMO"
    ERROR = "ERROR"


class DataQualityResult(BaseModel):
    state: DataQualityState
    source: str
    observed_at: Optional[datetime] = None
    age_seconds: Optional[float] = Field(default=None, ge=0)
    reason: str
    usable_for_verified_savings: bool = False


def classify_telemetry(
    *,
    value: Optional[float],
    observed_at: Optional[datetime],
    source: str,
    now: Optional[datetime] = None,
    max_age_seconds: int = 300,
    demo: bool = False,
    error: bool = False,
) -> DataQualityResult:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if demo:
        return DataQualityResult(state=DataQualityState.DEMO, source=source, reason="Demo data is not live telemetry")
    if error:
        return DataQualityResult(state=DataQualityState.ERROR, source=source, reason="Source reported an error")
    if value is None or not isfinite(value) or observed_at is None:
        return DataQualityResult(state=DataQualityState.NO_DATA, source=source, reason="Missing or invalid value/timestamp")
    if observed_at.tzinfo is None:
        return DataQualityResult(state=DataQualityState.NO_DATA, source=source, reason="Timestamp lacks timezone")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    age = (current - observed_at).total_seconds()
    if age < -60:
        return DataQualityResult(state=DataQualityState.ERROR, source=source, observed_at=observed_at, reason="Timestamp is in the future")
    age = max(age, 0.0)
    if age > max_age_seconds:
        return DataQualityResult(state=DataQualityState.STALE, source=source, observed_at=observed_at, age_seconds=age, reason="Reading exceeded freshness limit")
    return DataQualityResult(state=DataQualityState.LIVE, source=source, observed_at=observed_at, age_seconds=age, reason="Valid recent reading")
