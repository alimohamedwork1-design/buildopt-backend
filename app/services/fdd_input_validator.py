"""FDD input validation — readiness gate before rule execution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.data_quality_engine import QualityState, score_point

READINESS_READY = "READY"
READINESS_PARTIAL = "PARTIAL"
READINESS_BLOCKED = "BLOCKED"
READINESS_INSUFFICIENT = "INSUFFICIENT_DATA"

MIN_QUALITY_SCORE = 60.0
MIN_HISTORY_HOURS = 1


def validate_fdd_inputs(
    *,
    required_keys: List[str],
    optional_keys: Optional[List[str]] = None,
    readings: Dict[str, Any],
    point_meta: Optional[Dict[str, Dict[str, Any]]] = None,
    min_history_hours: int = MIN_HISTORY_HOURS,
    history_available_hours: Optional[float] = None,
    equipment_operating: Optional[bool] = None,
) -> Dict[str, Any]:
    """Return readiness status with explicit blocking reasons."""
    optional_keys = optional_keys or []
    point_meta = point_meta or {}
    reasons: List[str] = []
    missing: List[str] = []
    stale: List[str] = []
    bad_quality: List[str] = []
    unit_issues: List[str] = []

    for key in required_keys:
        if key not in readings or readings[key] is None:
            missing.append(key)
            continue
        meta = point_meta.get(key, {})
        pq = score_point(
            value=readings[key],
            quality=meta.get("quality") or meta.get("normalized_quality"),
            freshness_seconds=meta.get("freshness_seconds"),
            expected_interval_seconds=int(meta.get("expected_interval_seconds") or 300),
            unit=meta.get("unit"),
            expected_unit=meta.get("expected_unit"),
            variance=meta.get("variance"),
        )
        if pq["state"] in (QualityState.STALE.value, QualityState.NO_DATA.value):
            stale.append(key)
        if pq["score"] < MIN_QUALITY_SCORE:
            bad_quality.append(key)
        if "unit_mismatch" in pq.get("reasons", []):
            unit_issues.append(key)

    if missing:
        reasons.append(f"missing_required_inputs:{','.join(missing)}")
    if stale:
        reasons.append(f"stale_inputs:{','.join(stale)}")
    if bad_quality:
        reasons.append(f"low_quality_inputs:{','.join(bad_quality)}")
    if unit_issues:
        reasons.append(f"unit_mismatch:{','.join(unit_issues)}")
    if history_available_hours is not None and history_available_hours < min_history_hours:
        reasons.append(f"insufficient_history:{history_available_hours}h<{min_history_hours}h")
    if equipment_operating is False:
        reasons.append("equipment_not_operating")

    mapped_optional = sum(1 for k in optional_keys if k in readings and readings[k] is not None)
    coverage = 1.0 - (len(missing) / max(len(required_keys), 1))

    if missing:
        status = READINESS_INSUFFICIENT if len(missing) == len(required_keys) else READINESS_BLOCKED
    elif bad_quality or stale or unit_issues:
        status = READINESS_PARTIAL
    elif history_available_hours is not None and history_available_hours < min_history_hours:
        status = READINESS_PARTIAL
    else:
        status = READINESS_READY

    return {
        "status": status,
        "coverage": round(coverage, 2),
        "optional_coverage": mapped_optional,
        "reasons": reasons,
        "missing_keys": missing,
        "stale_keys": stale,
        "bad_quality_keys": bad_quality,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }
