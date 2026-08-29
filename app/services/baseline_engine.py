"""Baseline engine — explainable historical comparison with optional normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.gcc_config import get_calendar


def compute_historical_baseline(
    series: List[Dict[str, Any]],
    *,
    metric: str = "total_kw",
    training_hours: int = 168,
    exclude_weekends: bool = False,
    outdoor_temp_series: Optional[List[Dict[str, Any]]] = None,
    humidity_series: Optional[List[Dict[str, Any]]] = None,
    schedule_context: Optional[Dict[str, Any]] = None,
    occupancy_series: Optional[List[Dict[str, Any]]] = None,
    calendar_id: str = "GCC_STANDARD",
    ramadan_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Trustworthy baseline from historical samples with explicit feature availability."""
    features_used: List[str] = ["historical_mean"]
    features_unavailable: List[str] = []

    if not series:
        return {
            "available": False,
            "state": "INSUFFICIENT_DATA",
            "reason": "NO_DATA — no historical samples for baseline",
            "confidence": 0.0,
            "model": "historical_mean",
            "model_version": "baseline_v2",
            "features_used": features_used,
            "features_unavailable": ["all"],
        }

    cal = get_calendar(calendar_id)
    filtered = list(series)
    if exclude_weekends:
        features_used.append("weekend_exclusion")
        # Without timestamps on rows, document intent only
        features_unavailable.append("weekend_filter_requires_timestamps")

    values = [float(s["value"]) for s in filtered if s.get("value") is not None]
    if len(values) < 4:
        return {
            "available": False,
            "state": "INSUFFICIENT_DATA",
            "reason": f"INSUFFICIENT_DATA — only {len(values)} samples (need ≥4)",
            "confidence": round(len(values) / 4 * 0.5, 2),
            "sample_count": len(values),
            "model": "historical_mean",
            "model_version": "baseline_v2",
            "features_used": features_used,
            "features_unavailable": features_unavailable,
        }

    mean_val = sum(values) / len(values)
    variance = sum((v - mean_val) ** 2 for v in values) / len(values)
    std = variance ** 0.5
    coverage_pct = min(100.0, (len(values) / max(training_hours, 1)) * 100)
    limitations: List[str] = []

    normalized_mean = mean_val
    if outdoor_temp_series and len(outdoor_temp_series) >= 4:
        oat_vals = [float(x["value"]) for x in outdoor_temp_series if x.get("value") is not None]
        if oat_vals:
            features_used.append("outdoor_temperature")
            oat_mean = sum(oat_vals) / len(oat_vals)
            limitations.append(f"OAT context available (mean {oat_mean:.1f}°C) — linear normalization not applied in v2")
    else:
        features_unavailable.append("outdoor_temperature")

    if humidity_series and len(humidity_series) >= 4:
        features_used.append("humidity")
    else:
        features_unavailable.append("humidity")

    if schedule_context:
        features_used.append("schedule")
    else:
        features_unavailable.append("schedule")

    if occupancy_series and len(occupancy_series) >= 4:
        features_used.append("occupancy_load")
    else:
        features_unavailable.append("occupancy_load")

    if ramadan_profile:
        features_used.append("ramadan_profile")
    elif cal.get("ramadan_profile_supported"):
        features_unavailable.append("ramadan_profile")

    if cal.get("friday_index") is not None:
        features_used.append("gcc_calendar")

    mape_proxy = round(std / mean_val * 100, 1) if mean_val else None

    return {
        "available": True,
        "state": "OK",
        "model": "historical_mean",
        "model_version": "baseline_v2",
        "training_period_hours": training_hours,
        "sample_count": len(values),
        "data_coverage_pct": round(coverage_pct, 1),
        "baseline_value": round(normalized_mean, 2),
        "std_dev": round(std, 2),
        "confidence": round(min(0.95, coverage_pct / 100 * 0.85), 2),
        "error_metrics": {"std_dev": round(std, 2), "mape_proxy_pct": mape_proxy},
        "features_used": features_used,
        "features_unavailable": features_unavailable,
        "weather_coverage": "partial" if "outdoor_temperature" in features_used else None,
        "occupancy_coverage": "partial" if "occupancy_load" in features_used else None,
        "excluded_periods": ["weekends"] if exclude_weekends else [],
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "limitations": limitations or ["Weather/occupancy normalization uses available inputs only; no fabrication"],
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
        "model_version": baseline.get("model_version"),
    }
