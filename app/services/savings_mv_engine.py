"""Savings & M&V engine — POTENTIAL != VERIFIED."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.baseline_engine import compute_historical_baseline, deviation_from_baseline
from app.services.savings_engine import SavingsOpportunity, SavingsState, compute_opportunity

_OPPORTUNITIES: Dict[str, SavingsOpportunity] = {}


def create_potential_savings(
    *,
    opp_id: str,
    building_id: str,
    title: str,
    baseline_kwh: float,
    expected_kwh: float,
    tariff_aed: float = 0.38,
    data_coverage_pct: float = 0,
    recommendation_id: Optional[str] = None,
) -> SavingsOpportunity:
    if data_coverage_pct < 50:
        raise ValueError("INSUFFICIENT_DATA — coverage below 50% for savings claim")
    opp = compute_opportunity(
        opp_id=opp_id,
        building_id=building_id,
        title=title,
        baseline_kwh=baseline_kwh,
        expected_kwh=expected_kwh,
        tariff=tariff_aed,
        data_coverage_pct=data_coverage_pct,
    )
    opp.state = SavingsState.POTENTIAL
    _OPPORTUNITIES[opp.id] = opp
    return opp


def verify_savings(
    opp_id: str,
    *,
    actual_kwh: float,
    measurement_days: int,
    min_days: int = 14,
) -> SavingsOpportunity:
    opp = _OPPORTUNITIES.get(opp_id)
    if not opp:
        raise ValueError("opportunity_not_found")
    if measurement_days < min_days:
        opp.state = SavingsState.MONITORING
        opp.notes = f"MONITORING — {measurement_days}/{min_days} days collected"
        return opp
    avoided = max(0.0, opp.baseline_kwh - actual_kwh)
    opp.actual_kwh = actual_kwh
    opp.avoided_kwh = avoided
    opp.verified_saving_aed = round(avoided * opp.tariff_aed_per_kwh, 2)
    opp.state = SavingsState.VERIFIED if avoided > 0 else SavingsState.REJECTED
    opp.notes = f"Verified over {measurement_days} days"
    return opp


def savings_from_baseline(
    *,
    opp_id: str,
    building_id: str,
    title: str,
    current_kwh: float,
    history_series: List[Dict[str, Any]],
    tariff_aed: float = 0.38,
) -> Dict[str, Any]:
    baseline = compute_historical_baseline(history_series)
    if not baseline.get("available"):
        return {"state": "INSUFFICIENT_DATA", "reason": baseline.get("reason"), "opportunity": None}
    dev = deviation_from_baseline(current_kwh, baseline)
    if not dev.get("available"):
        return {"state": "INSUFFICIENT_DATA", "reason": dev.get("reason"), "opportunity": None}
    expected = baseline["baseline_value"]
    opp = create_potential_savings(
        opp_id=opp_id,
        building_id=building_id,
        title=title,
        baseline_kwh=current_kwh,
        expected_kwh=expected,
        tariff_aed=tariff_aed,
        data_coverage_pct=baseline.get("data_coverage_pct", 0),
    )
    return {"state": "POTENTIAL", "opportunity": opp.model_dump(mode="json"), "deviation": dev}


def list_mv_opportunities(building_id: Optional[str] = None) -> List[SavingsOpportunity]:
    items = list(_OPPORTUNITIES.values())
    if building_id:
        items = [o for o in items if o.building_id == building_id]
    return items
