"""Production report generation — live data only, honest limitations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.baseline_engine import compute_historical_baseline
from app.services.fdd_fault_store import get_fdd_fault_store
from app.services.recommendations_store import list_recommendations
from app.services.savings_mv_engine import list_mv_opportunities
from app.services.telemetry_store import get_telemetry_store
from app.services.data_quality_engine import aggregate_scores, score_point


def building_performance_report(building_id: str, *, hours: int = 168) -> Dict[str, Any]:
    ts = get_telemetry_store()
    points, total = ts.list_points(building_id=building_id, limit=200)
    scores = []
    for p in points:
        st = ts.get_current_state(p["id"])
        if not st:
            continue
        scores.append(score_point(
            value=st.get("last_value"),
            quality=st.get("normalized_quality"),
            freshness_seconds=st.get("freshness_seconds"),
        ))
    health = aggregate_scores(scores, label=building_id)
    return {
        "report_type": "building_performance",
        "building_id": building_id,
        "period_hours": hours,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_coverage": {"mapped_points": total, "with_current_state": len(scores)},
        "quality": health,
        "limitations": ["Potential savings not included", "Weather normalization not applied"],
    }


def fdd_report(building_id: str) -> Dict[str, Any]:
    faults = get_fdd_fault_store().list_all(building_id)
    return {
        "report_type": "fdd",
        "building_id": building_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_faults": len([f for f in faults if f.get("status") not in ("RESOLVED", "CLOSED")]),
        "faults": faults,
        "limitations": ["Based on approved semantic mappings only"],
    }


def executive_pilot_report(building_id: str) -> Dict[str, Any]:
    perf = building_performance_report(building_id)
    fdd = fdd_report(building_id)
    recs = list_recommendations(building_id)
    savings = list_mv_opportunities(building_id)
    potential = sum(o.expected_saving_aed for o in savings if o.state.value == "POTENTIAL")
    verified = sum(o.verified_saving_aed or 0 for o in savings if o.state.value == "VERIFIED")
    return {
        "report_type": "executive_pilot",
        "building_id": building_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "connected": perf["data_coverage"]["with_current_state"] > 0,
        "data_trustworthy": perf["quality"]["score"] >= 60,
        "active_faults": fdd["active_faults"],
        "recommendations": len(recs),
        "potential_savings_aed": potential,
        "verified_savings_aed": verified,
        "limitations": [
            "Potential savings ≠ verified savings",
            "FDD requires approved semantic inputs",
            "Customer-site Metasys validation pending",
        ],
    }
