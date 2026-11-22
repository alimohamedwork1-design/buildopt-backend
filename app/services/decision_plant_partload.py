"""Decision OS: bounded, read-only chiller plant PART-LOAD scenario review.

Inputs are manually entered assumptions, not SCADA measurements or a calibrated
performance map. No run/stop, setpoint, sequencing or equipment commands.
"""
from __future__ import annotations

from itertools import combinations
from typing import Literal
from pydantic import Field, model_validator

from app.services.decision_engine import StrictModel, SourceMode, _common


class PlantChiller(StrictModel):
    unit_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    rated_cooling_kw: float = Field(gt=0, le=20000)
    cop_at_25_pct: float = Field(ge=1, le=12)
    cop_at_50_pct: float = Field(ge=1, le=12)
    cop_at_100_pct: float = Field(ge=1, le=12)
    minimum_load_fraction: float = Field(ge=0.25, le=0.60)
    auxiliary_power_kw: float = Field(ge=0, le=2000)
    available: bool = True
    locked_out: bool = False
    currently_running: bool = False


class PlantPartLoadRequest(StrictModel):
    building_id: str = Field(min_length=1, max_length=128)
    required_cooling_kw: float = Field(ge=0, le=80000)
    chillers: list[PlantChiller] = Field(min_length=1, max_length=8)
    spare_capacity_fraction: float = Field(ge=0, le=0.4)
    max_new_starts: int = Field(ge=0, le=8)
    duration_hours: float = Field(gt=0, le=24)
    startup_energy_kwh: float = Field(ge=0, le=500)
    engineering_limits_reviewed: bool = False
    site_interlocks_reviewed: bool = False
    source_mode: SourceMode
    read_only: Literal[True] = True

    @model_validator(mode="after")
    def ids_unique(self):
        ids = [item.unit_id for item in self.chillers]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate chiller identifiers")
        return self


def _cop(c: PlantChiller, fraction: float) -> float:
    """Piecewise-linear assumed COP between three user-entered points."""
    if fraction <= 0.5:
        w = (fraction - 0.25) / 0.25
        return c.cop_at_25_pct + w * (c.cop_at_50_pct - c.cop_at_25_pct)
    w = (fraction - 0.5) / 0.5
    return c.cop_at_50_pct + w * (c.cop_at_100_pct - c.cop_at_50_pct)


def review_plant_part_load(p: PlantPartLoadRequest) -> dict:
    common = _common(p.source_mode, p.building_id, "chiller_part_load_review")
    assumptions = [
        "Illustrative engineering assumptions only; entered COP points are NOT field calibrated.",
        "Each candidate uses proportional loading across selected chillers; this is NOT global optimal dispatch.",
        "Auxiliary pump/tower kW is assumed constant per active unit; no hydraulic, condenser-water or ambient model.",
        "Unselected AVAILABLE units contribute a modeled spare-capacity check, not a validated N+1 reliability design.",
        "Operator review flags are unverified declarations. No interlocks, minimum run/off times, ramps or pressure limits are enforced.",
        "No control commands, live BMS access, verified performance or guaranteed savings.",
    ]
    base = {**common, "model_calibrated": False, "plant_safety_certified": False,
            "best": None, "candidates": [], "assumptions": assumptions}
    if not p.engineering_limits_reviewed or not p.site_interlocks_reviewed:
        return {**base, "feasible": False,
                "blockers": ["engineering_limits_and_site_interlocks_not_reviewed"]}
    ready = [c for c in p.chillers if c.available and not c.locked_out]
    if p.required_cooling_kw == 0:
        return {**base, "feasible": True, "blockers": [],
                "best": {"unit_ids": [], "electric_power_kw": 0, "modeled_energy_kwh": 0,
                         "starts": 0, "dispatch": []}}
    candidates = []
    for count in range(1, len(ready) + 1):
        for group in combinations(ready, count):
            rated = sum(c.rated_cooling_kw for c in group)
            spare = sum(c.rated_cooling_kw for c in ready if c not in group)
            if rated + 1e-9 < p.required_cooling_kw:
                continue
            if spare + 1e-9 < p.required_cooling_kw * p.spare_capacity_fraction:
                continue
            starts = sum(not c.currently_running for c in group)
            if starts > p.max_new_starts:
                continue
            fraction = p.required_cooling_kw / rated
            if any(fraction + 1e-9 < c.minimum_load_fraction for c in group):
                continue
            dispatch = []
            power = 0.0
            for c in group:
                load = p.required_cooling_kw * c.rated_cooling_kw / rated
                cop = _cop(c, fraction)
                power += load / cop + c.auxiliary_power_kw
                dispatch.append({"unit_id": c.unit_id, "assumed_cooling_kw": round(load, 3),
                                 "assumed_part_load_fraction": round(fraction, 4),
                                 "interpolated_assumed_cop": round(cop, 3)})
            energy = power * p.duration_hours + starts * p.startup_energy_kwh
            candidates.append({
                "unit_ids": [c.unit_id for c in group],
                "electric_power_kw": round(power, 3),
                "modeled_energy_kwh": round(energy, 3),
                "assumed_unused_spare_capacity_kw": round(spare, 3),
                "starts": starts, "dispatch": dispatch,
            })
    candidates.sort(key=lambda x: (x["modeled_energy_kwh"], x["starts"], x["unit_ids"]))
    return {**base, "feasible": bool(candidates),
            "blockers": [] if candidates else ["no_subset_respects_part_load_spare_and_start_constraints"],
            "best": candidates[0] if candidates else None,
            "candidates": candidates[:8]}
