"""Telemetry validation, event IDs, and three-timestamp provenance."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_event_id(
    *,
    gateway_id: str,
    building_id: str,
    connector_id: str,
    source_point_id: str,
    source_timestamp: str,
    value: Any,
) -> str:
    raw = f"{gateway_id}|{building_id}|{connector_id}|{source_point_id}|{source_timestamp}|{value}"
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_reading(reading: Dict[str, Any]) -> Dict[str, Any]:
    if not reading.get("building_id"):
        raise ValueError("building_id required")
    source_point_id = reading.get("source_point_id") or reading.get("point_id")
    if not source_point_id:
        raise ValueError("source_point_id required")
    edge_received_at = reading.get("edge_received_at") or _utcnow_iso()
    source_timestamp = reading.get("source_timestamp") or reading.get("timestamp")
    if not source_timestamp:
        reading["source_timestamp_missing"] = True
        source_timestamp = edge_received_at
    value = reading.get("value")
    if value is None:
        raise ValueError("value required")
    reading["source_point_id"] = str(source_point_id)
    reading["source_timestamp"] = source_timestamp
    reading["edge_received_at"] = edge_received_at
    reading.setdefault("quality", "UNCERTAIN")
    reading.setdefault("source", "metasys")
    if not reading.get("event_id"):
        reading["event_id"] = stable_event_id(
            gateway_id=str(reading.get("gateway_id") or ""),
            building_id=str(reading["building_id"]),
            connector_id=str(reading.get("connector_id") or "metasys"),
            source_point_id=str(source_point_id),
            source_timestamp=str(source_timestamp),
            value=value,
        )
    return reading


def normalize_batch(
    readings: List[Dict[str, Any]],
    building_id: str,
    gateway_id: str,
    connector_id: str,
    tenant_id: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for raw in readings:
        row = validate_reading(
            {
                **raw,
                "building_id": raw.get("building_id") or building_id,
                "gateway_id": gateway_id,
                "connector_id": connector_id,
                "tenant_id": tenant_id,
            }
        )
        out.append(row)
    return out
