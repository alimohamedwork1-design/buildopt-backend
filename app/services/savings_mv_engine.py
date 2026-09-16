"""Savings & M&V engine — POTENTIAL != VERIFIED, durable and lifecycle-gated."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.baseline_engine import compute_historical_baseline, deviation_from_baseline
from app.services.savings_engine import (
    SavingsOpportunity,
    SavingsState,
    compute_opportunity,
    get_opportunity,
    list_opportunities,
    transition_savings,
    upsert_opportunity,
)


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
    if baseline_kwh <= 0:
        raise ValueError("INSUFFICIENT_DATA — positive baseline required for savings claim")
    if expected_kwh < 0:
        raise ValueError("invalid_expected_kwh")
    if data_coverage_pct < 50:
        raise ValueError("INSUFFICIENT_DATA — coverage below 50% for savings claim")
    return compute_opportunity(
        opp_id=opp_id,
        building_id=building_id,
        title=title,
        baseline_kwh=baseline_kwh,
        expected_kwh=expected_kwh,
        tariff=tariff_aed,
        data_coverage_pct=data_coverage_pct,
        recommendation_id=recommendation_id,
    )


def verify_savings(
    opp_id: str,
    *,
    actual_kwh: float,
    measurement_days: int,
    min_days: int = 14,
) -> SavingsOpportunity:
    """Record/verify a measurement period without bypassing the M&V lifecycle.

    Only IMPLEMENTED or MONITORING opportunities may enter measurement. A short
    period remains MONITORING. A complete period can become VERIFIED or REJECTED.
    """
    opp = get_opportunity(opp_id)
    if not opp:
        raise ValueError("opportunity_not_found")
    if actual_kwh < 0:
        raise ValueError("invalid_actual_kwh")
    if measurement_days < 0:
        raise ValueError("invalid_measurement_days")
    if opp.state not in (SavingsState.IMPLEMENTED, SavingsState.MONITORING):
        raise ValueError(f"verification_requires_implemented_or_monitoring:{opp.state.value}")
    if opp.baseline_kwh <= 0:
        raise ValueError("verification_requires_positive_baseline")

    if opp.state == SavingsState.IMPLEMENTED:
        opp = transition_savings(
            opp_id,
            SavingsState.MONITORING,
            comment="M&V measurement period started",
        )

    opp.actual_kwh = float(actual_kwh)
    opp.after_energy_kwh = float(actual_kwh)
    opp.notes = f"MONITORING — {measurement_days}/{min_days} days collected"
    opp.verification_status = "MONITORING"
    opp = upsert_opportunity(opp)

    if measurement_days < min_days:
        return opp

    avoided = max(0.0, opp.baseline_kwh - actual_kwh)
    opp.actual_kwh = actual_kwh
    opp.after_energy_kwh = actual_kwh
    opp.avoided_kwh = avoided
    opp.energy_saved_kwh = avoided
    opp.verified_saving_aed = round(avoided * opp.tariff_aed_per_kwh, 2)
    opp.cost_saved = opp.verified_saving_aed
    opp.notes = f"Measurement period complete: {measurement_days} days"
    opp = upsert_opportunity(opp)

    target = SavingsState.VERIFIED if avoided > 0 else SavingsState.REJECTED
    saved = transition_savings(
        opp_id,
        target,
        comment=f"M&V completed over {measurement_days} days; avoided_kwh={avoided:.3f}",
    )
    saved.notes = f"Verified over {measurement_days} days" if target == SavingsState.VERIFIED else f"No verified savings over {measurement_days} days"
    return upsert_opportunity(saved)


def savings_from_baseline(
    *,
    opp_id: str,
    building_id: str,
    title: str,
    current_kwh: float,
    history_series: List[Dict[str, Any]],
    tariff_aed: float = 0.38,
    recommendation_id: Optional[str] = None,
) -> Dict[str, Any]:
    baseline = compute_historical_baseline(history_series)
    if not baseline.get("available"):
        return {"state": "INSUFFICIENT_DATA", "reason": baseline.get("reason"), "opportunity": None}
    dev = deviation_from_baseline(current_kwh, baseline)
    if not dev.get("available"):
        return {"state": "INSUFFICIENT_DATA", "reason": dev.get("reason"), "opportunity": None}

    # This creates a POTENTIAL comparison only. It must never be presented as
    # verified savings until implementation + measurement complete.
    observed = float(current_kwh)
    expected = float(baseline["baseline_value"])
    high = max(observed, expected)
    low = min(observed, expected)
    if high <= 0 or high == low:
        return {"state": "NO_OPPORTUNITY", "reason": "no_positive_baseline_delta", "opportunity": None, "deviation": dev}

    opp = create_potential_savings(
        opp_id=opp_id,
        building_id=building_id,
        title=title,
        baseline_kwh=high,
        expected_kwh=low,
        tariff_aed=tariff_aed,
        data_coverage_pct=baseline.get("data_coverage_pct", 0),
        recommendation_id=recommendation_id,
    )
    return {"state": "POTENTIAL", "opportunity": opp.model_dump(mode="json"), "deviation": dev}


def list_mv_opportunities(building_id: Optional[str] = None) -> List[SavingsOpportunity]:
    return list_opportunities(building_id)
