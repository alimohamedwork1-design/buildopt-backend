"""Evidence-first, deterministic HVAC investigation assistant.

This is not an LLM or a controls optimizer. It never queries the customer's
network, sends commands, estimates guaranteed savings, or fabricates telemetry.
Only explicitly supplied, quality-checked evidence may inform findings.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceQuality(str, Enum):
    GOOD = "good"
    STALE = "stale"
    MISSING = "missing"
    INVALID = "invalid"
    UNCERTAIN = "uncertain"


class MeasuredPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    point_id: str = Field(min_length=2, max_length=160)
    equipment_id: str = Field(min_length=2, max_length=160)
    kind: Literal[
        "chw_supply_c", "chw_return_c", "power_kw", "flow_m3h",
        "ahu_supply_c", "ahu_return_c", "status", "other",
    ]
    value: float | None = None
    unit: str = Field(min_length=1, max_length=20)
    quality: EvidenceQuality
    measured_at: datetime
    received_at: datetime
    processed_at: datetime

    @model_validator(mode="after")
    def timestamp_order(self):
        if any(x.tzinfo is None or x.utcoffset() is None for x in (self.measured_at,self.received_at,self.processed_at)):
            raise ValueError("Evidence timestamps must include explicit timezone offsets")
        if not self.measured_at <= self.received_at <= self.processed_at:
            raise ValueError("Timestamp order must be measured <= received <= processed")
        return self


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    building_id: str = Field(min_length=1, max_length=160)
    equipment_id: str = Field(min_length=2, max_length=160)
    equipment_type: Literal["chiller_plant", "air_handling_unit", "other"]
    declared_operating_mode: Literal["cooling", "heating", "unknown"] = "unknown"
    operator_min_cooling_delta_c: float | None = Field(default=None, ge=0.5, le=20.0)
    points: list[MeasuredPoint] = Field(min_length=1, max_length=100)
    explicitly_authorized_data: Literal[True] = True
    mode: Literal["read_only"] = "read_only"


def _eligible(point: MeasuredPoint, now: datetime, freshness_minutes: int) -> bool:
    if point.value is None or point.quality != EvidenceQuality.GOOD:
        return False
    measured=point.measured_at
    if measured.tzinfo is None:
        return False
    if point.received_at > now + timedelta(minutes=1) or point.processed_at > now + timedelta(minutes=1):
        return False
    if measured > now + timedelta(minutes=1):
        return False
    if now-measured > timedelta(minutes=freshness_minutes):
        return False
    return True


def analyze_evidence(payload: InvestigationRequest, *, now: datetime | None=None) -> dict:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Analysis clock must be timezone-aware")
    points=[p for p in payload.points if p.equipment_id==payload.equipment_id]
    latest: dict[str,MeasuredPoint] = {}
    rejected: list[dict] = []
    for p in points:
        if not _eligible(p,now,15):
            rejected.append({"point_id":p.point_id,"reason":"quality_or_freshness_failed"})
            continue
        old=latest.get(p.kind)
        if old is None or p.measured_at>old.measured_at:
            latest[p.kind]=p
    findings: list[dict] = []
    def add(code:str,severity:str,description:str,refs:list[MeasuredPoint],next_check:str):
        findings.append({
            "code":code,"severity":severity,"description":description,
            "point_ids":[p.point_id for p in refs],
            "sample_timestamps":[p.measured_at.isoformat() for p in refs],
            "next_check":next_check,"confidence":"rule_observation_only",
            "verified_savings":None,"action_requires_engineer":True
        })

    if payload.equipment_type=="chiller_plant":
        supply=latest.get("chw_supply_c")
        ret=latest.get("chw_return_c")
        if supply and ret:
            if abs((supply.measured_at-ret.measured_at).total_seconds())>120:
                add("UNALIGNED_CHW_SAMPLES","blocked",
                    "Supply and return samples differ by more than two minutes; no delta-T calculation.",
                    [supply,ret],"Acquire time-aligned, quality-approved readings before causal review.")
            elif supply.unit != "°C" or ret.unit!="°C":
                add("INVALID_UNITS","warning",
                    "Temperature points have inconsistent or unsupported units.",[supply,ret],
                    "Check sensor units and semantic mappings; no delta-T analysis performed.")
            else:
                delta=ret.value-supply.value # type: ignore[operator]
                if not (-3<=supply.value<=45 and -3<=ret.value<=55):  # type: ignore[operator]
                    add("IMPLAUSIBLE_TEMPERATURE","warning",
                        "One or more CHW temperatures are outside this conservative investigation range.",
                        [supply,ret],"Inspect sensor placement, units and calibration.")
                elif delta < 0:
                    add("REVERSED_CHW_DELTA","warning",
                        f"Return minus supply = {delta:.1f} °C (negative).",
                        [supply,ret],"Verify point labels, flow direction, operating state and sensor calibration.")
                elif delta < 3:
                    add("LOW_CHW_DELTA","review",
                        f"Observed CHW delta-T = {delta:.1f} °C (below the illustrative 3 °C review threshold).",
                        [supply,ret],"Review load, flow, valve bypass and operating mode with the site engineer; confirm plant-specific threshold.")
                else:
                    add("CHW_DELTA_OBSERVED","info",
                        f"Observed CHW delta-T = {delta:.1f} °C. No low-delta-T finding by this illustrative threshold.",
                        [supply,ret],"Compare with plant design and validated baseline before concluding performance.")
        else:
            missing=[kind for kind in ("chw_supply_c","chw_return_c") if kind not in latest]
            add("INSUFFICIENT_CHW_EVIDENCE","blocked",
                "Unable to evaluate chilled-water delta-T; missing quality-approved fresh readings: "+", ".join(missing),
                [x for x in (supply,ret) if x],"Collect approved point mapping and fresh supply/return readings.")
    elif payload.equipment_type=="air_handling_unit":
        supply=latest.get("ahu_supply_c")
        ret=latest.get("ahu_return_c")
        if not supply or not ret:
            missing=[kind for kind in ("ahu_supply_c","ahu_return_c") if kind not in latest]
            add("INSUFFICIENT_AHU_EVIDENCE","blocked",
                "Unable to compare AHU air temperatures; missing fresh, good-quality readings: "+", ".join(missing),
                [x for x in (supply,ret) if x],"Collect mapped, current AHU supply and return temperature samples.")
        elif abs((supply.measured_at-ret.measured_at).total_seconds())>120:
            add("UNALIGNED_AHU_SAMPLES","blocked",
                "AHU supply and return temperatures differ in timestamp by more than two minutes.",
                [supply,ret],"Capture synchronized readings before reviewing air temperature separation.")
        elif supply.unit!="°C" or ret.unit!="°C":
            add("INVALID_AHU_UNITS","blocked",
                "AHU air temperatures have unsupported or inconsistent units.",
                [supply,ret],"Validate source units and semantic mappings.")
        elif not (-20<=supply.value<=70 and -20<=ret.value<=70):
            add("IMPLAUSIBLE_AHU_TEMPERATURE","blocked",
                "AHU air temperatures are outside a conservative investigation range.",
                [supply,ret],"Verify sensors and units; reject this comparison.")
        else:
            delta=ret.value-supply.value
            if payload.declared_operating_mode=="cooling" and payload.operator_min_cooling_delta_c is not None:
                if delta<payload.operator_min_cooling_delta_c:
                    add("AHU_COOLING_DELTA_REVIEW","review",
                        f"Observed return-minus-supply = {delta:.1f} °C, below the operator-stated "+
                        f"{payload.operator_min_cooling_delta_c:.1f} °C review threshold.",
                        [supply,ret],"Confirm AHU operating mode, sensor location, damper/valve conditions and design delta; not a fault diagnosis.")
                else:
                    add("AHU_COOLING_DELTA_OBSERVED","info",
                        f"Observed return-minus-supply = {delta:.1f} °C; exceeds stated illustrative threshold.",
                        [supply,ret],"Confirm with design airflow and independent commissioning data.")
            else:
                add("AHU_TEMPERATURE_DIFFERENCE_ONLY","info",
                    f"Observed AHU return-minus-supply = {delta:.1f} °C. Cooling-mode threshold not established.",
                    [supply,ret],"Declare valid heating/cooling operating mode and a site-specific threshold before fault review.")
    else:
        add("NO_ENGINEERING_RULE","blocked",
            "No validated equipment-specific rule is available in this assessment version.",
            [],"Assign a documented engineering rule and approved inputs before requesting a finding.")

    return {
        "building_id":payload.building_id,"equipment_id":payload.equipment_id,
        "evaluation":"illustrative_engineering_rule_not_certified",
        "data_source":"caller_supplied_authorized_points",
        "read_only":True,"control_commands":[],"automated_writeback":False,
        "analyzed_at":now.isoformat(),"received_point_count":len(payload.points),
        "used_point_ids":sorted({p.point_id for p in latest.values()}),
        "rejected_points":rejected,"findings":findings,
        "overall_status":"insufficient_data" if any(f["severity"]=="blocked" for f in findings) else "review_required",
        "disclaimer":"Observations are not root-cause confirmation, modeled savings or field acceptance. A qualified engineer must validate site design and measurements.",
    }
