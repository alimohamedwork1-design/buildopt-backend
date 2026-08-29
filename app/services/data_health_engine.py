"""Point-level and aggregated data health engine."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.data_quality import DataQuality, assess_point


def assess_point_health(
    *,
    value: Any,
    timestamp: Optional[datetime] = None,
    expected_interval_seconds: int = 300,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    variance: Optional[float] = None,
) -> Dict[str, Any]:
    quality = assess_point(
        value,
        timestamp=timestamp,
        min_value=min_value,
        max_value=max_value,
        expected_interval_seconds=expected_interval_seconds,
    )
    flags: List[str] = []
    if variance is not None and variance == 0 and isinstance(value, (int, float)):
        flags.append("flatline")

    status_map = {
        DataQuality.GOOD: "GOOD",
        DataQuality.STALE: "STALE",
        DataQuality.MISSING: "OFFLINE",
        DataQuality.INVALID: "INVALID",
        DataQuality.OUT_OF_RANGE: "INVALID",
        DataQuality.COMMUNICATION_ERROR: "OFFLINE",
        DataQuality.UNKNOWN: "UNKNOWN",
    }
    status = status_map.get(quality, "UNKNOWN")
    if flags and status == "GOOD":
        status = "DEGRADED"

    freshness_seconds = None
    if timestamp:
        freshness_seconds = int((datetime.now(timezone.utc) - timestamp).total_seconds())

    return {
        "status": status,
        "quality": quality.value,
        "freshness_seconds": freshness_seconds,
        "availability_pct": 100.0 if value is not None else 0.0,
        "flags": flags,
    }


def aggregate_health(point_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not point_results:
        return {"status": "UNKNOWN", "availability_pct": 0.0, "point_count": 0}

    total = len(point_results)
    good = sum(1 for p in point_results if p.get("status") == "GOOD")
    stale = sum(1 for p in point_results if p.get("status") == "STALE")
    offline = sum(1 for p in point_results if p.get("status") in ("OFFLINE", "UNKNOWN"))

    availability = round((good / total) * 100, 1)
    if offline > total * 0.5:
        status = "OFFLINE"
    elif stale > total * 0.3:
        status = "STALE"
    elif good / total >= 0.9:
        status = "GOOD"
    else:
        status = "DEGRADED"

    return {
        "status": status,
        "availability_pct": availability,
        "point_count": total,
        "good_points": good,
        "stale_points": stale,
        "offline_points": offline,
    }


def registry_point_health(point: Dict[str, Any]) -> Dict[str, Any]:
    """Assess health for a Phase 3 registry point with current state."""
    current = point.get("current") or {}
    val = current.get("last_value")
    if val is None:
        val = current.get("last_value_text")
    ts = current.get("last_source_timestamp") or current.get("last_cloud_received_at")
    parsed_ts = None
    if ts:
        try:
            parsed_ts = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if parsed_ts.tzinfo is None:
                parsed_ts = parsed_ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            parsed_ts = None

    interval = point.get("expected_interval_seconds") or current.get("expected_interval_seconds") or 300
    health = assess_point_health(
        value=val,
        timestamp=parsed_ts,
        expected_interval_seconds=int(interval),
    )
    freshness_state = current.get("freshness_state")
    if freshness_state == "STALE":
        health["status"] = "STALE"
    elif freshness_state == "OFFLINE":
        health["status"] = "OFFLINE"
    elif freshness_state == "LIVE" and health["status"] in ("UNKNOWN", "OFFLINE"):
        health["status"] = "GOOD"

    return {
        "point_id": point.get("id"),
        "point_key": point.get("source_name") or point.get("source_point_id"),
        "source_point_id": point.get("source_point_id"),
        "source": point.get("source"),
        "semantic_key": (point.get("metadata") or {}).get("semantic_key"),
        "gateway_id": point.get("gateway_id"),
        "connector_id": point.get("connector_id"),
        "freshness_state": freshness_state,
        "last_value": val,
        "last_source_timestamp": current.get("last_source_timestamp"),
        "last_cloud_received_at": current.get("last_cloud_received_at"),
        "source_quality": current.get("source_quality"),
        "normalized_quality": current.get("normalized_quality"),
        "expected_interval_seconds": interval,
        **health,
    }


def registry_building_data_health(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    point_results = [registry_point_health(p) for p in points if p]
    return {
        "building_summary": aggregate_health(point_results),
        "points": point_results,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "source": "registry",
    }


def building_data_health(
    mapped_points: Dict[str, Any],
    live_values: Dict[str, Any],
    *,
    observed_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    ts = observed_at or datetime.now(timezone.utc)
    point_results: List[Dict[str, Any]] = []

    for key in mapped_points:
        raw = live_values.get(key)
        val = raw.get("value") if isinstance(raw, dict) else raw
        point_results.append({"point_key": key, **assess_point_health(value=val, timestamp=ts)})

    return {
        "building_summary": aggregate_health(point_results),
        "points": point_results,
        "computed_at": ts.isoformat(),
    }
