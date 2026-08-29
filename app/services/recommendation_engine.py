"""Recommendation engine — evidence-backed actions from FDD faults."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.recommendations_store import Recommendation, RecommendationState, upsert_recommendation


RECOMMENDATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "AHU-001": {"title": "Investigate SAT deviation", "action": "Check SAT sensor calibration and cooling valve response"},
    "AHU-003": {"title": "Fix simultaneous heating/cooling", "action": "Review valve interlocks and control sequence"},
    "AHU-005": {"title": "Replace or clean air filter", "action": "Inspect filter DP and schedule replacement"},
    "CH-002": {"title": "Address low delta-T", "action": "Review CHW flow, valve positions, and load distribution"},
    "default": {"title": "Investigate equipment fault", "action": "Review FDD evidence and inspect equipment"},
}


def recommendation_from_fault(fault: Dict[str, Any]) -> Recommendation:
    tpl = RECOMMENDATION_TEMPLATES.get(fault.get("rule_id", ""), RECOMMENDATION_TEMPLATES["default"])
    return Recommendation(
        id=f"rec_{secrets.token_hex(6)}",
        building_id=fault.get("building_id", ""),
        title=tpl["title"],
        description=tpl["action"],
        state=RecommendationState.RECOMMENDED,
        severity=fault.get("severity", "warning"),
        evidence={
            "fault_id": fault.get("fault_id"),
            "rule_id": fault.get("rule_id"),
            "observed_values": fault.get("observed_values", {}),
            "confidence": fault.get("confidence"),
            "data_quality_score": fault.get("data_quality_score"),
        },
        fault_id=fault.get("fault_id"),
        expected_saving_aed=None,
    )


def generate_recommendations_from_faults(faults: List[Dict[str, Any]]) -> List[Recommendation]:
    recs: List[Recommendation] = []
    for fault in faults:
        if fault.get("severity") in ("critical", "warning"):
            rec = recommendation_from_fault(fault)
            upsert_recommendation(rec)
            recs.append(rec)
    return recs
