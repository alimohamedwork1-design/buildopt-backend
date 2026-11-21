"""BuildOpt Decision OS v1 — bounded, read-only *illustrative* engineering solvers.

These services do not open network connections, change BMS setpoints, persist
operational state, verify meter data, or certify IPMVP savings. All numeric
results describe the assumptions explicitly supplied by the caller.
"""
from __future__ import annotations

from itertools import combinations
from math import isclose
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Currency = Literal["EGP", "SAR", "AED", "USD", "QAR", "EUR"]
SourceMode = Literal["synthetic_demo", "operator_assumptions"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class ChillerUnit(StrictModel):
    unit_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    cooling_capacity_kw: float = Field(gt=0, le=20000)
    reference_cop: float = Field(ge=1.0, le=12.0)
    min_load_fraction: float = Field(ge=0, le=0.6)
    available: bool = True
    currently_running: bool = False


class ChillerDispatchRequest(StrictModel):
    building_id: str = Field(min_length=1, max_length=128)
    demand_cooling_kw: float = Field(ge=0, le=80000)
    chillers: list[ChillerUnit] = Field(min_length=1, max_length=8)
    tariff_per_kwh: float = Field(ge=0, le=1000)
    currency: Currency = "USD"
    duration_hours: float = Field(gt=0, le=24)
    startup_penalty_kwh: float = Field(ge=0, le=200)
    reserve_margin_fraction: float = Field(ge=0, le=0.4)
    assumed_baseline_power_kw: float | None = Field(default=None, gt=0, le=80000)
    source_mode: SourceMode
    read_only: Literal[True] = True

    @model_validator(mode="after")
    def unique_units(self):
        ids = [item.unit_id for item in self.chillers]
        if len(ids) != len(set(ids)):
            raise ValueError("Chiller unit identifiers must be unique")
        return self


class ScheduleRequest(StrictModel):
    building_id: str = Field(min_length=1, max_length=128)
    occupancy_hours: float = Field(ge=0, le=24)
    preconditioning_hours: float = Field(ge=0, le=12)
    baseline_run_hours: float = Field(ge=0, le=24)
    proposed_run_hours: float = Field(ge=0, le=24)
    assumed_active_power_kw: float = Field(ge=0, le=80000)
    tariff_per_kwh: float = Field(ge=0, le=1000)
    currency: Currency = "USD"
    source_mode: SourceMode
    read_only: Literal[True] = True


class FaultCandidate(StrictModel):
    fault_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    asset_id: str = Field(min_length=1, max_length=64)
    severity: int = Field(ge=1, le=5)
    asset_criticality: int = Field(ge=1, le=5)
    age_days: int = Field(ge=0, le=365)
    evidence_quality: Literal["accepted", "uncertain", "missing"] = "missing"
    safety_related: bool = False


class FaultPriorityRequest(StrictModel):
    building_id: str = Field(min_length=1, max_length=128)
    faults: list[FaultCandidate] = Field(min_length=1, max_length=30)
    source_mode: SourceMode
    read_only: Literal[True] = True

    @model_validator(mode="after")
    def unique_faults(self):
        ids = [item.fault_id for item in self.faults]
        if len(set(ids)) != len(ids):
            raise ValueError("Fault IDs must be unique")
        return self


def _common(source_mode: SourceMode, building_id: str, engine: str) -> dict:
    return {
        "engine": engine,
        "building_id": building_id,
        "status": "illustrative_assumption_model",
        "source_mode": source_mode,
        "field_validated": False,
        "savings_verified": False,
        "recommendations_require_engineer": True,
        "writeback_enabled": False,
        "control_commands": [],
    }


def optimize_chiller_dispatch(request: ChillerDispatchRequest) -> dict:
    """Enumerate 2^n on/off groups, greedily allocate residual load by COP.

    For the stated constant reference COP and startup penalty assumptions,
    this is exact for each enumerated subset. It is *not* nonlinear MPC,
    verified COP at partial load, or an instruction to switch equipment.
    """
    base = _common(request.source_mode, request.building_id, "chiller_dispatch")
    available = [c for c in request.chillers if c.available]
    rated_available = sum(c.cooling_capacity_kw for c in available)
    required_capacity = request.demand_cooling_kw * (1 + request.reserve_margin_fraction)
    if rated_available + 1e-8 < required_capacity:
        return {**base, "feasible": False, "blockers": ["insufficient_available_capacity_including_reserve"],
                "available_capacity_kw": round(rated_available, 3),
                "required_capacity_kw": round(required_capacity, 3),
                "candidates": [], "best": None,
                "assumptions": ["Constant reference COP; no field calibration." ]}
    if request.demand_cooling_kw == 0:
        return {**base, "feasible": True, "blockers": [], "available_capacity_kw": round(rated_available, 3),
                "required_capacity_kw": 0.0, "candidates": [],
                "best": {"electric_power_kw": 0.0, "modeled_energy_kwh": 0.0,
                         "modeled_cost": 0.0, "indicative_delta_cost": None,
                         "dispatch": [], "starts": 0},
                "assumptions": ["Zero assumed thermal demand; all units remain off."]}

    candidates: list[dict] = []
    for count in range(1, len(available) + 1):
        for group in combinations(available, count):
            min_load = sum(c.cooling_capacity_kw * c.min_load_fraction for c in group)
            max_load = sum(c.cooling_capacity_kw for c in group)
            if request.demand_cooling_kw + 1e-8 < min_load or max_load + 1e-8 < required_capacity:
                continue
            remaining = request.demand_cooling_kw - min_load
            loads = {c.unit_id: c.cooling_capacity_kw * c.min_load_fraction for c in group}
            for c in sorted(group, key=lambda x: (-x.reference_cop, x.unit_id)):
                extra = min(remaining, c.cooling_capacity_kw - loads[c.unit_id])
                loads[c.unit_id] += extra
                remaining -= extra
            if remaining > 1e-6:
                continue
            power = sum(loads[c.unit_id] / c.reference_cop for c in group)
            starts = sum(not c.currently_running for c in group)
            energy = power * request.duration_hours + starts * request.startup_penalty_kwh
            baseline = request.assumed_baseline_power_kw
            delta = None if baseline is None else (baseline * request.duration_hours - energy) * request.tariff_per_kwh
            candidates.append({
                "unit_ids": [c.unit_id for c in group],
                "dispatch": [{"unit_id": c.unit_id,
                              "cooling_load_kw": round(loads[c.unit_id], 3),
                              "load_fraction": round(loads[c.unit_id] / c.cooling_capacity_kw, 4),
                              "assumed_reference_cop": c.reference_cop} for c in group],
                "electric_power_kw": round(power, 3),
                "modeled_energy_kwh": round(energy, 3),
                "modeled_cost": round(energy * request.tariff_per_kwh, 2),
                "indicative_delta_cost": None if delta is None else round(delta, 2),
                "starts": starts,
            })
    candidates.sort(key=lambda item: (item["modeled_energy_kwh"], item["starts"], item["unit_ids"]))
    return {
        **base, "feasible": bool(candidates),
        "blockers": [] if candidates else ["no_group_respects_minimum_load_and_reserve"],
        "available_capacity_kw": round(rated_available, 3),
        "required_capacity_kw": round(required_capacity, 3),
        "candidates": candidates[:8],
        "best": candidates[0] if candidates else None,
        "currency": request.currency,
        "assumptions": [
            "User-entered fixed thermal load, constant reference COP per unit, and flat tariff.",
            "Minimum load and capacity reserve are enforced; startup energy penalty is assumed.",
            "No weather, part-load COP curve, hydraulics, reliability, temperature constraints or automatic commands.",
            "An indicative delta is shown only against an explicitly supplied, unverified baseline power.",
        ],
    }


def assess_hvac_schedule(request: ScheduleRequest) -> dict:
    base = _common(request.source_mode, request.building_id, "hvac_scheduling")
    minimum = request.occupancy_hours + request.preconditioning_hours
    if minimum > 24 or request.proposed_run_hours + 1e-9 < minimum:
        return {**base, "feasible": False, "blockers": ["proposed_hours_below_occupied_plus_preconditioning"],
                "best": None, "required_run_hours": round(minimum, 3)}
    if request.baseline_run_hours + 1e-9 < minimum:
        return {**base, "feasible": False, "blockers": ["baseline_hours_below_occupied_plus_preconditioning"],
                "best": None, "required_run_hours": round(minimum, 3)}
    baseline = request.baseline_run_hours * request.assumed_active_power_kw
    proposed = request.proposed_run_hours * request.assumed_active_power_kw
    return {
        **base, "feasible": True, "blockers": [],
        "required_run_hours": round(minimum, 3), "currency": request.currency,
        "best": {
            "baseline_energy_kwh": round(baseline, 3),
            "proposed_energy_kwh": round(proposed, 3),
            "indicative_energy_difference_kwh": round(baseline - proposed, 3),
            "indicative_cost_difference": round((baseline-proposed)*request.tariff_per_kwh, 2),
            "comfort_verified": False,
        },
        "assumptions": [
            "Daily run-hour comparison, not a time-resolved thermostat or weather model.",
            "Constant manually assumed active power; time of day and tariff shape are not modeled.",
            "Occupancy and preconditioning minimum are enforced; physical comfort remains unverified.",
        ],
    }


def prioritize_faults(request: FaultPriorityRequest) -> dict:
    items = []
    for item in request.faults:
        score = round(4*item.severity*item.asset_criticality + min(item.age_days,30)/10, 1)
        items.append({
            "fault_id": item.fault_id, "asset_id": item.asset_id,
            "relative_risk_score": score, "safety_related": item.safety_related,
            "evidence_quality": item.evidence_quality,
            "review_action": "safety_escalation" if item.safety_related else
                "verify_evidence" if item.evidence_quality != "accepted" else "engineer_triage",
            "score_is_probability": False, "automated_work_order": False,
        })
    items.sort(key=lambda x: (not x["safety_related"], -x["relative_risk_score"], x["fault_id"]))
    return {
        **_common(request.source_mode, request.building_id, "fault_prioritization"),
        "feasible": True, "blockers": [],
        "ranked_faults": items, "best": None,
        "assumptions": [
            "Ordinal heuristic: 4 × severity × criticality plus capped age factor.",
            "Relative score is NOT a failure probability, predicted downtime, or calibrated financial loss.",
            "Safety-related findings are escalated first independent of score.",
            "Never clear or reset equipment alarms automatically.",
        ],
    }
