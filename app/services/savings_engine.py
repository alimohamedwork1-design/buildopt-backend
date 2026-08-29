"""Transparent savings pipeline — potential vs verified, durable storage."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.services.telemetry_store import get_telemetry_store

VALID_SAVINGS_TRANSITIONS: Dict[str, frozenset] = {
    "POTENTIAL": frozenset({"APPROVED", "REJECTED"}),
    "APPROVED": frozenset({"IMPLEMENTED", "REJECTED"}),
    "IMPLEMENTED": frozenset({"MONITORING", "REJECTED"}),
    "MONITORING": frozenset({"VERIFIED", "REJECTED"}),
    "VERIFIED": frozenset(),
    "REJECTED": frozenset(),
}


class SavingsState(str, Enum):
    POTENTIAL = "POTENTIAL"
    APPROVED = "APPROVED"
    IMPLEMENTED = "IMPLEMENTED"
    MONITORING = "MONITORING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class SavingsOpportunity(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    building_id: str
    recommendation_id: Optional[str] = None
    title: str
    state: SavingsState = SavingsState.POTENTIAL
    baseline_kwh: float = 0
    expected_kwh: float = 0
    actual_kwh: Optional[float] = None
    avoided_kwh: Optional[float] = None
    tariff_aed_per_kwh: float = 0.38
    expected_saving_aed: float = 0
    verified_saving_aed: Optional[float] = None
    confidence: float = 0.5
    methodology: str = "baseline_comparison"
    data_coverage_pct: float = 0
    notes: Optional[str] = None
    measurement_period_start: Optional[datetime] = None
    measurement_period_end: Optional[datetime] = None
    implementation_date: Optional[datetime] = None
    before_energy_kwh: Optional[float] = None
    after_energy_kwh: Optional[float] = None
    normalized_baseline_kwh: Optional[float] = None
    weather_context: Dict[str, Any] = Field(default_factory=dict)
    schedule_context: Dict[str, Any] = Field(default_factory=dict)
    energy_saved_kwh: Optional[float] = None
    cost_saved: Optional[float] = None
    currency: str = "AED"
    uncertainty: Optional[float] = None
    verification_status: Optional[str] = None
    excluded_periods: List[str] = Field(default_factory=list)
    calculation_version: str = "mv_v1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _store():
    return get_telemetry_store()


def _to_model(row: Dict[str, Any]) -> SavingsOpportunity:
    data = dict(row)
    data["state"] = SavingsState(data.get("state", "POTENTIAL"))
    for key in (
        "created_at", "updated_at", "measurement_period_start", "measurement_period_end",
        "implementation_date",
    ):
        if data.get(key) and isinstance(data[key], str):
            try:
                data[key] = datetime.fromisoformat(str(data[key]).replace("Z", "+00:00"))
            except ValueError:
                pass
    return SavingsOpportunity.model_validate(data)


def _to_row(opp: SavingsOpportunity) -> Dict[str, Any]:
    d = opp.model_dump(mode="json")
    d["state"] = opp.state.value
    return d


def compute_opportunity(
    *,
    opp_id: str,
    building_id: str,
    title: str,
    baseline_kwh: float,
    expected_kwh: float,
    tariff: float = 0.38,
    data_coverage_pct: float = 100.0,
    recommendation_id: Optional[str] = None,
) -> SavingsOpportunity:
    avoided = max(0.0, baseline_kwh - expected_kwh)
    opp = SavingsOpportunity(
        id=opp_id,
        building_id=building_id,
        recommendation_id=recommendation_id,
        title=title,
        state=SavingsState.POTENTIAL,
        baseline_kwh=baseline_kwh,
        expected_kwh=expected_kwh,
        avoided_kwh=avoided,
        tariff_aed_per_kwh=tariff,
        expected_saving_aed=round(avoided * tariff, 2),
        confidence=min(0.95, data_coverage_pct / 100 * 0.9),
        data_coverage_pct=data_coverage_pct,
        before_energy_kwh=baseline_kwh,
        normalized_baseline_kwh=expected_kwh,
        verification_status="POTENTIAL",
    )
    row = _store().upsert_savings_opportunity(_to_row(opp))
    return _to_model(row)


def list_opportunities(building_id: Optional[str] = None, *, limit: int = 100) -> List[SavingsOpportunity]:
    rows = _store().list_savings_opportunities(building_id, limit=limit)
    return [_to_model(r) for r in rows]


def get_opportunity(opp_id: str) -> Optional[SavingsOpportunity]:
    row = _store().get_savings_opportunity(opp_id)
    return _to_model(row) if row else None


def upsert_opportunity(opp: SavingsOpportunity) -> SavingsOpportunity:
    opp.updated_at = datetime.now(timezone.utc)
    row = _store().upsert_savings_opportunity(_to_row(opp))
    return _to_model(row)


def transition_savings(
    opp_id: str,
    new_state: SavingsState,
    *,
    actor_user_id: Optional[str] = None,
    comment: Optional[str] = None,
) -> SavingsOpportunity:
    opp = get_opportunity(opp_id)
    if not opp:
        raise ValueError("opportunity_not_found")
    prev = opp.state.value
    allowed = VALID_SAVINGS_TRANSITIONS.get(prev, frozenset())
    if new_state.value not in allowed:
        raise ValueError(f"invalid_transition:{prev}->{new_state.value}")
    opp.state = new_state
    opp.verification_status = new_state.value
    saved = upsert_opportunity(opp)
    _store().insert_savings_audit(
        audit_id=f"sa_{secrets.token_hex(8)}",
        savings_id=opp_id,
        action=f"transition_{new_state.value}",
        previous_state=prev,
        new_state=new_state.value,
        actor_user_id=actor_user_id,
        comment=comment,
    )
    return saved
