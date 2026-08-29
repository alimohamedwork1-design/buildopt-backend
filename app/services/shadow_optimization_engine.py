"""Shadow optimization — recommendations only, no BMS writeback."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.baseline_engine import compute_historical_baseline
from app.services.write_policy import DEFAULT_WRITE_MODE, WriteMode


def shadow_optimize(
    *,
    building_id: str,
    current_setpoints: Dict[str, float],
    constraints: Dict[str, Any],
    history_series: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Calculate recommended setpoints without applying them.
    Uses engineering rules only — no MPC unless data sufficiency supports it.
    """
    if DEFAULT_WRITE_MODE == WriteMode.READ_ONLY:
        mode = "SHADOW_ONLY"

    recommendations: List[Dict[str, Any]] = []
    baseline = compute_historical_baseline(history_series or [])

    sat = current_setpoints.get("supply_air_setpoint")
    if sat is not None and sat < constraints.get("min_supply_temp", 18):
        recommendations.append({
            "parameter": "supply_air_setpoint",
            "current": sat,
            "recommended": constraints["min_supply_temp"],
            "reason": "Below comfort minimum bound",
            "predicted_impact_kwh": None,
            "confidence": 0.7 if baseline.get("available") else 0.3,
        })
    elif sat is not None and baseline.get("available"):
        energy = baseline.get("baseline_value", 0)
        if energy > 0:
            recommendations.append({
                "parameter": "supply_air_setpoint",
                "current": sat,
                "recommended": round(sat + 0.5, 1),
                "reason": "SAT reset opportunity — reduce cooling load",
                "predicted_impact_kwh": round(energy * 0.02, 1),
                "confidence": baseline.get("confidence", 0.5),
            })

    chws_sp = current_setpoints.get("chws_setpoint")
    if chws_sp is not None:
        recommendations.append({
            "parameter": "chws_setpoint",
            "current": chws_sp,
            "recommended": round(min(chws_sp + 0.5, constraints.get("max_chws_temp", 8)), 1),
            "reason": "CHW reset opportunity if load permits",
            "predicted_impact_kwh": None,
            "confidence": 0.4,
            "limitations": ["Requires verified load data"],
        })

    return {
        "building_id": building_id,
        "mode": mode,
        "writeback_enabled": False,
        "candidates": recommendations,
        "constraints_applied": constraints,
        "baseline_confidence": baseline.get("confidence"),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
