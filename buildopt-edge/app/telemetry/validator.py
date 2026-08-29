"""Telemetry validation and normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def validate_reading(reading: Dict[str, Any]) -> Dict[str, Any]:
    if not reading.get("building_id"):
        raise ValueError("building_id required")
    if not reading.get("point_id"):
        raise ValueError("point_id required")
    ts = reading.get("timestamp")
    if not ts:
        reading["timestamp"] = datetime.now(timezone.utc).isoformat()
    value = reading.get("value")
    if value is None:
        raise ValueError("value required")
    reading.setdefault("quality", "GOOD")
    reading.setdefault("source", "metasys")
    return reading


def normalize_batch(readings: List[Dict[str, Any]], building_id: str, gateway_id: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for raw in readings:
        row = validate_reading({**raw, "building_id": raw.get("building_id") or building_id})
        row["gateway_id"] = gateway_id
        out.append(row)
    return out
