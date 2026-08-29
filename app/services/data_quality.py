"""Telemetry quality states and validation."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class DataQuality(str, Enum):
    GOOD = "GOOD"
    STALE = "STALE"
    MISSING = "MISSING"
    INVALID = "INVALID"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    COMMUNICATION_ERROR = "COMMUNICATION_ERROR"
    UNKNOWN = "UNKNOWN"


def assess_point(
    value: Any,
    *,
    timestamp: Optional[datetime] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    expected_interval_seconds: int = 300,
    now: Optional[datetime] = None,
) -> DataQuality:
    if value is None:
        return DataQuality.MISSING
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return DataQuality.INVALID
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return DataQuality.INVALID
    if min_value is not None and numeric < min_value:
        return DataQuality.OUT_OF_RANGE
    if max_value is not None and numeric > max_value:
        return DataQuality.OUT_OF_RANGE
    if timestamp is not None:
        ref = now or datetime.now(timezone.utc)
        age = (ref - timestamp).total_seconds()
        if age > expected_interval_seconds * 3:
            return DataQuality.STALE
    return DataQuality.GOOD


def quality_payload(quality: DataQuality, **meta: Any) -> Dict[str, Any]:
    return {"quality": quality.value, **meta}
