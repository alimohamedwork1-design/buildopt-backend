"""Telemetry quality enum and normalization."""

from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple


class TelemetryQuality(str, Enum):
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"
    STALE = "STALE"
    NO_DATA = "NO_DATA"
    INVALID = "INVALID"
    COMM_ERROR = "COMM_ERROR"


_SOURCE_MAP = {
    "good": TelemetryQuality.GOOD,
    "ok": TelemetryQuality.GOOD,
    "uncertain": TelemetryQuality.UNCERTAIN,
    "bad": TelemetryQuality.BAD,
    "stale": TelemetryQuality.STALE,
    "no_data": TelemetryQuality.NO_DATA,
    "nodata": TelemetryQuality.NO_DATA,
    "invalid": TelemetryQuality.INVALID,
    "comm_error": TelemetryQuality.COMM_ERROR,
    "error": TelemetryQuality.COMM_ERROR,
    "offline": TelemetryQuality.COMM_ERROR,
}


def normalize_quality(raw: Optional[str], *, has_value: bool = True) -> Tuple[str, str]:
    """Return (source_quality, normalized_quality). Never invent GOOD without evidence."""
    if raw is None or str(raw).strip() == "":
        if not has_value:
            return ("", TelemetryQuality.NO_DATA.value)
        return ("", TelemetryQuality.UNCERTAIN.value)
    source = str(raw).strip()
    key = source.lower().replace("-", "_").replace(" ", "_")
    normalized = _SOURCE_MAP.get(key, TelemetryQuality.UNCERTAIN)
    return (source, normalized.value)


def quality_allows_storage(normalized_quality: str) -> bool:
    return normalized_quality not in (TelemetryQuality.INVALID.value,)
