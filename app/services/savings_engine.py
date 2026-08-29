"""Transparent savings pipeline — potential vs verified."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SavingsState(str, Enum):
    POTENTIAL = "POTENTIAL"
    APPROVED = "APPROVED"
    IMPLEMENTED = "IMPLEMENTED"
    MONITORING = "MONITORING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class SavingsOpportunity(BaseModel):
    id: str
    building_id: str
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def compute_opportunity(
    *,
    opp_id: str,
    building_id: str,
    title: str,
    baseline_kwh: float,
    expected_kwh: float,
    tariff: float = 0.38,
    data_coverage_pct: float = 100.0,
) -> SavingsOpportunity:
    avoided = max(0.0, baseline_kwh - expected_kwh)
    return SavingsOpportunity(
        id=opp_id,
        building_id=building_id,
        title=title,
        state=SavingsState.POTENTIAL,
        baseline_kwh=baseline_kwh,
        expected_kwh=expected_kwh,
        avoided_kwh=avoided,
        tariff_aed_per_kwh=tariff,
        expected_saving_aed=round(avoided * tariff, 2),
        confidence=min(0.95, data_coverage_pct / 100 * 0.9),
        data_coverage_pct=data_coverage_pct,
    )


_OPPORTUNITIES: Dict[str, SavingsOpportunity] = {}


def list_opportunities(building_id: Optional[str] = None) -> List[SavingsOpportunity]:
    items = list(_OPPORTUNITIES.values())
    if building_id:
        items = [o for o in items if o.building_id == building_id]
    return items
