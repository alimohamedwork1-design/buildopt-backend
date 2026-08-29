"""Operational observability counters — no credentials in logs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

_COUNTERS: Dict[str, int] = {
    "mapping_suggestions_generated": 0,
    "mapping_approved": 0,
    "mapping_rejected": 0,
    "mapping_reverted": 0,
    "config_publish_total": 0,
    "config_refresh_success": 0,
    "config_refresh_failure": 0,
    "history_query_total": 0,
    "history_query_latency_ms_sum": 0,
    "fdd_evaluations": 0,
    "fdd_faults_detected": 0,
    "baseline_computations": 0,
    "recommendations_generated": 0,
}


def increment(counter: str, amount: int = 1) -> None:
    _COUNTERS[counter] = _COUNTERS.get(counter, 0) + amount


def record_latency(counter_prefix: str, latency_ms: int) -> None:
    increment(f"{counter_prefix}_total")
    _COUNTERS[f"{counter_prefix}_latency_ms_sum"] = _COUNTERS.get(f"{counter_prefix}_latency_ms_sum", 0) + latency_ms


def snapshot() -> Dict[str, Any]:
    history_total = _COUNTERS.get("history_query_total", 0)
    latency_sum = _COUNTERS.get("history_query_latency_ms_sum", 0)
    return {
        "counters": dict(_COUNTERS),
        "history_avg_latency_ms": round(latency_sum / history_total, 1) if history_total else None,
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
    }
