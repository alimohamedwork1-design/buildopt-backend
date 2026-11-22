"""BuildOpt Decision OS V2: strictly read-only, user-assumption scenario models.

No live site access, calibrated performance guarantee, control writeback, legal
tariff verification, refrigeration safety certification or verified savings.
The numeric results are conditional on explicitly submitted assumptions.
"""
from __future__ import annotations

from itertools import combinations
from typing import Literal

from pydantic import Field, model_validator

from app.services.decision_engine import Currency, SourceMode, StrictModel, _common


class TariffProfileRequest(StrictModel):
    building_id: str = Field(min_length=1, max_length=128)
    currency: Currency = "USD"
    baseline_hourly_kwh: list[float] = Field(min_length=24, max_length=24)
    proposed_hourly_kwh: list[float] = Field(min_length=24, max_length=24)
    hourly_rate_per_kwh: list[float] = Field(min_length=24, max_length=24)
    peak_limit_kw: float | None = Field(default=None, gt=0, le=1_000_000)
    demand_charge_per_kw_for_period: float = Field(default=0, ge=0, le=100000)
    tax_fraction: float = Field(default=0, ge=0, le=0.5)
    source_mode: SourceMode
    read_only: Literal[True] = True

    @model_validator(mode="after")
    def positive_inputs(self):
        if any(x < 0 or x > 1_000_000 for x in self.baseline_hourly_kwh + self.proposed_hourly_kwh):
            raise ValueError("Each hourly kWh value must be between 0 and 1,000,000")
        if any(x < 0 or x > 1000 for x in self.hourly_rate_per_kwh):
            raise ValueError("Each hourly rate must be between 0 and 1000")
        return self


def analyze_tariff_profile(p: TariffProfileRequest) -> dict:
    """Compare two 24-hour user-entered load curves and a 24-hour rate curve.

    Hourly energy divided by one hour is a *proxy* for average kW and cannot
    establish actual 15-minute measured utility billing demand.
    """
    base = _common(p.source_mode, p.building_id, "tou_energy_cost")
    baseline_energy = sum(p.baseline_hourly_kwh)
    proposed_energy = sum(p.proposed_hourly_kwh)
    base_peak = max(p.baseline_hourly_kwh)
    new_peak = max(p.proposed_hourly_kwh)
    blocked_hours = [
        hour for hour, average_kw in enumerate(p.proposed_hourly_kwh)
        if p.peak_limit_kw is not None and average_kw > p.peak_limit_kw + 1e-9
    ]
    def costs(hours: list[float]) -> dict:
        energy_charge = sum(kwh * rate for kwh, rate in zip(hours,p.hourly_rate_per_kwh))
        peak_proxy = max(hours)
        demand_charge = peak_proxy * p.demand_charge_per_kw_for_period
        subtotal = energy_charge + demand_charge
        return {
            "energy_charge": round(energy_charge, 2),
            "demand_charge_proxy": round(demand_charge, 2),
            "tax_estimate": round(subtotal*p.tax_fraction, 2),
            "total_modeled_cost": round(subtotal*(1+p.tax_fraction), 2),
        }
    before = costs(p.baseline_hourly_kwh)
    after = costs(p.proposed_hourly_kwh)
    feasible = not blocked_hours
    return {
        **base, "feasible": feasible,
        "blockers": [] if feasible else ["hourly_average_peak_constraint_exceeded"],
        "violating_hour_indices": blocked_hours,
        "currency": p.currency,
        "comparison": {
            "baseline_kwh": round(baseline_energy,3),
            "proposed_kwh": round(proposed_energy,3),
            "baseline_hourly_average_peak_kw": round(base_peak,3),
            "proposed_hourly_average_peak_kw": round(new_peak,3),
            "baseline": before, "proposed": after,
            "indicative_cost_difference": round(before["total_modeled_cost"]-after["total_modeled_cost"],2),
        },
        "best": None,
        "assumptions": [
            "Hourly kWh is modeled as one-hour average kW; actual demand peaks can be higher.",
            "The supplied tariff and per-period demand fee are not independently verified against utility contracts.",
            "No taxes, taxes exemptions, fixed fees, ratchets, reactive charges, seasonality or settlement guarantees beyond inputs.",
            "No device schedules or dispatch instructions are generated; even favorable cost differences are not verified savings.",
        ],
    }


class CompressorUnit(StrictModel):
    unit_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    rated_cooling_kw: float = Field(gt=0, le=30000)
    assumed_cop: float = Field(ge=0.5, le=10)
    min_load_fraction: float = Field(ge=0, le=0.7)
    available: bool = True
    safety_locked_out: bool = False
    currently_running: bool = False


class RefrigerationAdvisoryRequest(StrictModel):
    building_id: str = Field(min_length=1, max_length=128)
    medium: Literal["R717","CO2","other"]
    assumed_cooling_demand_kw: float = Field(ge=0, le=100000)
    compressors: list[CompressorUnit] = Field(min_length=1, max_length=8)
    availability_reserve_fraction: float = Field(ge=0, le=0.4)
    duration_hours: float = Field(gt=0, le=24)
    startup_energy_kwh_per_start: float = Field(ge=0, le=500)
    site_safety_interlocks_reviewed: bool = False
    operating_envelope_approved: bool = False
    source_mode: SourceMode
    read_only: Literal[True] = True

    @model_validator(mode="after")
    def unique_compressors(self):
        ids = [c.unit_id for c in self.compressors]
        if len(ids) != len(set(ids)):
            raise ValueError("Compressor identifiers must be unique")
        return self


def review_refrigeration_staging(p: RefrigerationAdvisoryRequest) -> dict:
    """Constrained theoretical compressor staging advisory, NOT a PLC sequence.

    Mandatory operator flags prevent outputs being mistaken for an approved
    ammonia/CO2 operating sequence. Flags remain user claims, not signed proof.
    """
    base = _common(p.source_mode,p.building_id,"industrial_cooling_advisory")
    assumptions = [
        "Fixed user-entered cooling demand and constant hypothetical compressor COP.",
        "No economizer, staging interlocks, suction/discharge pressure, oil, liquid carryover, defrost or pressure relief model.",
        "Safety/operating-envelope booleans are unverified user declarations, not evidence of an approved controls design.",
        "No PLC commands or sequencing setpoints. A qualified refrigeration engineer must approve a real-site case.",
    ]
    if not p.site_safety_interlocks_reviewed or not p.operating_envelope_approved:
        return {**base,"feasible":False,"blockers":["site_safety_and_operating_limits_not_reviewed"],
                "candidates":[],"best":None,"assumptions":assumptions,"medium":p.medium}
    active=[c for c in p.compressors if c.available and not c.safety_locked_out]
    required=p.assumed_cooling_demand_kw*(1+p.availability_reserve_fraction)
    rated=sum(c.rated_cooling_kw for c in active)
    if rated+1e-9 < required:
        return {**base,"feasible":False,"blockers":["insufficient_unlocked_capacity_with_reserve"],
                "available_capacity_kw":round(rated,3),"required_capacity_kw":round(required,3),
                "candidates":[],"best":None,"assumptions":assumptions,"medium":p.medium}
    if p.assumed_cooling_demand_kw==0:
        return {**base,"feasible":True,"blockers":[],"best":{
            "unit_ids":[],"modeled_energy_kwh":0.0,"electric_power_kw":0.0,
            "starts":0,"dispatch":[]},"candidates":[],"assumptions":assumptions,"medium":p.medium}
    candidates=[]
    for k in range(1,len(active)+1):
        for group in combinations(active,k):
            min_load=sum(c.rated_cooling_kw*c.min_load_fraction for c in group)
            max_load=sum(c.rated_cooling_kw for c in group)
            if min_load>p.assumed_cooling_demand_kw+1e-9 or max_load+1e-9<required:
                continue
            loads={c.unit_id:c.rated_cooling_kw*c.min_load_fraction for c in group}
            remaining=p.assumed_cooling_demand_kw-min_load
            for c in sorted(group,key=lambda c:(-c.assumed_cop,c.unit_id)):
                extra=min(remaining,c.rated_cooling_kw-loads[c.unit_id])
                loads[c.unit_id]+=extra
                remaining-=extra
            if remaining>1e-6:
                continue
            power=sum(loads[c.unit_id]/c.assumed_cop for c in group)
            starts=sum(not c.currently_running for c in group)
            energy=power*p.duration_hours+starts*p.startup_energy_kwh_per_start
            candidates.append({
                "unit_ids":[c.unit_id for c in group],
                "electric_power_kw":round(power,3),
                "modeled_energy_kwh":round(energy,3),
                "starts":starts,
                "dispatch":[{"unit_id":c.unit_id,"cooling_kw":round(loads[c.unit_id],3)}
                            for c in group],
            })
    candidates.sort(key=lambda c:(c["modeled_energy_kwh"],c["starts"],c["unit_ids"]))
    return {
        **base,"feasible":bool(candidates),
        "blockers":[] if candidates else ["minimum_load_or_reserve_infeasible"],
        "medium":p.medium,
        "available_capacity_kw":round(rated,3),"required_capacity_kw":round(required,3),
        "best":candidates[0] if candidates else None,"candidates":candidates[:8],
        "assumptions":assumptions,
    }
