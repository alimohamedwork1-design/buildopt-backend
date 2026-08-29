"""Freshness calculation for telemetry points."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def compute_freshness(
    *,
    last_cloud_received_at: Optional[datetime],
    expected_interval_seconds: int = 30,
    stale_multiplier: float = 2.0,
    offline_multiplier: float = 10.0,
) -> Dict[str, Any]:
    """Compute freshness_seconds and freshness_state from last cloud receipt."""
    now = datetime.now(timezone.utc)
    interval = max(5, expected_interval_seconds)
    stale_threshold = int(interval * stale_multiplier)
    offline_threshold = int(interval * offline_multiplier)

    if last_cloud_received_at is None:
        return {
            "freshness_seconds": None,
            "expected_interval_seconds": interval,
            "freshness_state": "NO_DATA",
            "state": "NO_DATA",
        }

    ts = last_cloud_received_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age = int((now - ts).total_seconds())

    if age <= stale_threshold:
        freshness_state = "LIVE"
        state = "LIVE"
    elif age <= offline_threshold:
        freshness_state = "STALE"
        state = "STALE"
    else:
        freshness_state = "OFFLINE"
        state = "OFFLINE"

    return {
        "freshness_seconds": age,
        "expected_interval_seconds": interval,
        "freshness_state": freshness_state,
        "state": state,
    }


def apply_quality_state(base_state: str, normalized_quality: str) -> str:
    if normalized_quality in ("BAD", "INVALID"):
        return "BAD_QUALITY"
    if normalized_quality == "COMM_ERROR":
        return "COMM_ERROR"
    if normalized_quality == "NO_DATA":
        return "NO_DATA"
    return base_state
