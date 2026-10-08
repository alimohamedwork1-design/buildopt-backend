"""Authenticated, stateless read-only review calculations.

Inputs are caller-supplied; results are NEVER represented as measured site
telemetry, verified savings, or an equipment command.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.deps.auth import get_required_user
from app.models.user_context import UserContext
from app.services.measurement_verification import calculate_eui, estimate_unverified_savings
from app.services.scenario_constraints import ReadOnlyScenario

router = APIRouter(prefix="/review", tags=["Read-only review"])


class EnergyDifferenceRequest(BaseModel):
    baseline_kwh: Optional[float] = Field(default=None, ge=0)
    measured_kwh: Optional[float] = Field(default=None, ge=0)
    baseline_adjusted: bool = False
    sufficient_coverage: bool = False


class EuiRequest(BaseModel):
    building_id: str = Field(min_length=1)
    energy_kwh: float = Field(ge=0)
    conditioned_area_m2: float = Field(gt=0)


@router.post("/energy-difference")
async def energy_difference(body: EnergyDifferenceRequest, _user: UserContext = Depends(get_required_user)):
    result = estimate_unverified_savings(
        baseline_kwh=body.baseline_kwh, measured_kwh=body.measured_kwh,
        baseline_adjusted=body.baseline_adjusted, sufficient_coverage=body.sufficient_coverage,
    )
    return {"source": "USER_SUPPLIED", "verified": False, "result": vars(result) if result else None}


@router.post("/eui")
async def raw_eui(body: EuiRequest, _user: UserContext = Depends(get_required_user)):
    result = calculate_eui(
        building_id=body.building_id, energy_kwh=body.energy_kwh,
        conditioned_area_m2=body.conditioned_area_m2,
    )
    return {"source": "USER_SUPPLIED", "verified": False, "result": vars(result)}


@router.post("/scenario/validate")
async def scenario_validate(body: ReadOnlyScenario, _user: UserContext = Depends(get_required_user)):
    return {"mode": "READ_ONLY", "source": "USER_SUPPLIED", "scenario": body.model_dump()}
