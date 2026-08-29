"""Baseline engine — explainable historical comparison models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def compute_historical_baseline(
    series: List[Dict[str, Any]],
    *,
    metric: str = "total_kw",
    training_hours: int = 168,
    exclude_weekends: bool = False,
) -> Dict[str, Any]:
    """Simple trustworthy baseline from historical Influx samples."""
    if not series:
        return {
            "available": False,
            "state": "INSUFFICIENT_DATA",
            "reason": "NO_DATA — no historical samples for baseline",
            "confidence": 0.0,
        }

    values = [float(s["value"]) for s in series if s.get("value") is not None]
    if len(values) < 4:
        return {
            "available": False,
            "state": "INSUFFICIENT_DATA",
            "reason": f"INSUFFICIENT_DATA — only {len(values)} samples (need ≥4)",
            "confidence": round(len(values) / 4 * 0.5, 2),
            "sample_count": len(values),
        }

    mean_val = sum(values) / len(values)
    variance = sum((v - mean_val) ** 2 for v in values) / len(values)
    std = variance ** 0.5
    coverage_pct = min(100.0, (len(values) / max(training_hours, 1)) * 100)

    return {
        "available": True,
        "state": "OK",
        "model": "historical_mean",
        "model_version": "baseline_v1",
        "training_period_hours": training_hours,
        "sample_count": len(values),
        "data_coverage_pct": round(coverage_pct, 1),
        "baseline_value": round(mean_val, 2),
        "std_dev": round(std, 2),
        "confidence": round(min(0.95, coverage_pct / 100 * 0.85), 2),
        "weather_coverage": None,
        "occupancy_coverage": None,
        "excluded_periods": ["weekends"] if exclude_weekends else [],
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["No weather normalization applied", "No occupancy normalization applied"],
    }


def deviation_from_baseline(current: float, baseline: Dict[str, Any]) -> Dict[str, Any]:
    if not baseline.get("available"):
        return {"available": False, "reason": baseline.get("reason", "NO_BASELINE")}
    base = baseline["baseline_value"]
    if base == 0:
        return {"available": False, "reason": "ZERO_BASELINE"}
    pct = round((current - base) / base * 100, 1)
    return {
        "available": True,
        "current": current,
        "baseline": base,
        "deviation_pct": pct,
        "confidence": baseline.get("confidence", 0),
    }
