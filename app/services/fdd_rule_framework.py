"""Vendor-neutral FDD rule framework — deterministic rule definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from app.services.fdd_input_validator import validate_fdd_inputs

RuleCheck = Callable[[Dict[str, float], float], bool]


@dataclass
class FddRuleDefinition:
    rule_id: str
    equipment_type: str
    name: str
    required_inputs: List[str]
    optional_inputs: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    threshold: float = 0.0
    severity: str = "warning"
    persistence_cycles: int = 2
    min_confidence: float = 0.6
    check: str = ""
    description: str = ""


def _sat_deviation(r: Dict[str, float], t: float) -> bool:
    sat = r.get("supply_air_temp")
    sp = r.get("supply_air_setpoint") or r.get("sat_sp")
    if sat is None or sp is None:
        return False
    return abs(sat - sp) > t


def _simultaneous_heat_cool(r: Dict[str, float], _t: float) -> bool:
    h = r.get("heating_valve_cmd", 0)
    c = r.get("cooling_valve_cmd", 0) or r.get("chwv", 0)
    return h > 10 and c > 10


def _cooling_valve_leak(r: Dict[str, float], t: float) -> bool:
    cmd = r.get("cooling_valve_cmd", 0) or r.get("chwv", 0)
    sat = r.get("supply_air_temp")
    rat = r.get("return_air_temp")
    if sat is None or rat is None:
        return cmd > t
    return cmd < 5 and sat < rat - 2


def _fan_mismatch(r: Dict[str, float], _t: float) -> bool:
    cmd = r.get("fan_command", r.get("fan_cmd", 0))
    status = r.get("fan_status", 1)
    return (cmd > 0.5 and status < 0.5) or (cmd < 0.5 and status > 0.5)


def _filter_dp_high(r: Dict[str, float], t: float) -> bool:
    dp = r.get("filter_pressure_pa") or r.get("filter_dp")
    return dp is not None and dp > t


def _sensor_flatline(r: Dict[str, float], _t: float) -> bool:
    return r.get("sensor_variance", 1) == 0


def _static_pressure_tracking(r: Dict[str, float], t: float) -> bool:
    sp = r.get("static_pressure")
    sp_set = r.get("static_pressure_setpoint") or r.get("static_pressure_sp")
    if sp is None or sp_set is None:
        return False
    return abs(sp - sp_set) > t


def _oa_damper_mismatch(r: Dict[str, float], t: float) -> bool:
    cmd = r.get("oa_damper_cmd")
    fb = r.get("oa_damper_feedback")
    if cmd is None or fb is None:
        return False
    return abs(cmd - fb) > t


def _mat_inconsistency(r: Dict[str, float], t: float) -> bool:
    mat = r.get("mixed_air_temp") or r.get("mat")
    oat = r.get("outdoor_air_temp") or r.get("oat")
    rat = r.get("return_air_temp") or r.get("rat")
    oa_pct = r.get("oa_damper_feedback", r.get("oa_damper_cmd", 50))
    if mat is None or oat is None or rat is None:
        return False
    expected = oat * (oa_pct / 100) + rat * (1 - oa_pct / 100)
    return abs(mat - expected) > t


RULE_CHECKS: Dict[str, RuleCheck] = {
    "supply_air_temp_deviation": _sat_deviation,
    "sat_setpoint_tracking": _sat_deviation,
    "simultaneous_heating_cooling": _simultaneous_heat_cool,
    "cooling_valve_leakage": _cooling_valve_leak,
    "fan_status_mismatch": _fan_mismatch,
    "filter_dp_high": _filter_dp_high,
    "sensor_flatline": _sensor_flatline,
    "static_pressure_tracking": _static_pressure_tracking,
    "oa_damper_mismatch": _oa_damper_mismatch,
    "mat_inconsistency": _mat_inconsistency,
    "cop_degradation": lambda r, t: r.get("cop", 999) < t,
    "low_delta_t": lambda r, t: abs(r.get("chwr_temp", 0) - r.get("chws_temp", 0)) < t,
    "short_cycling": lambda r, t: r.get("compressor_starts_per_hr", 0) > t,
}


AHU_RULES: List[FddRuleDefinition] = [
    FddRuleDefinition("AHU-001", "AHU", "supply_air_temp_deviation", ["supply_air_temp", "supply_air_setpoint"], threshold=2.0, severity="warning", check="supply_air_temp_deviation", description="SAT deviates from setpoint"),
    FddRuleDefinition("AHU-002", "AHU", "sat_setpoint_tracking", ["supply_air_temp", "sat_sp"], threshold=2.0, severity="warning", check="sat_setpoint_tracking", description="SAT setpoint tracking failure"),
    FddRuleDefinition("AHU-003", "AHU", "simultaneous_heating_cooling", ["heating_valve_cmd", "cooling_valve_cmd"], threshold=1, severity="critical", check="simultaneous_heating_cooling", description="Simultaneous heating and cooling"),
    FddRuleDefinition("AHU-004", "AHU", "cooling_valve_leakage", ["cooling_valve_cmd", "supply_air_temp", "return_air_temp"], threshold=95, severity="warning", check="cooling_valve_leakage", description="Possible cooling valve leakage"),
    FddRuleDefinition("AHU-005", "AHU", "fan_status_mismatch", ["fan_command", "fan_status"], threshold=1, severity="warning", check="fan_status_mismatch", description="Fan command/status mismatch"),
    FddRuleDefinition("AHU-006", "AHU", "filter_dp_high", ["filter_pressure_pa"], threshold=250, severity="warning", check="filter_dp_high", description="High filter differential pressure"),
    FddRuleDefinition("AHU-007", "AHU", "static_pressure_tracking", ["static_pressure", "static_pressure_setpoint"], threshold=0.3, severity="warning", check="static_pressure_tracking", description="Static pressure setpoint tracking issue"),
    FddRuleDefinition("AHU-008", "AHU", "oa_damper_mismatch", ["oa_damper_cmd", "oa_damper_feedback"], threshold=15, severity="warning", check="oa_damper_mismatch", description="OA damper command/feedback mismatch"),
    FddRuleDefinition("AHU-009", "AHU", "mat_inconsistency", ["mixed_air_temp", "outdoor_air_temp", "return_air_temp"], threshold=3.0, severity="warning", check="mat_inconsistency", description="Mixed air temperature inconsistency"),
    FddRuleDefinition("AHU-010", "AHU", "sensor_flatline", ["sensor_variance"], threshold=1, severity="info", check="sensor_flatline", description="Sensor stuck / flatline"),
]

CHILLER_RULES: List[FddRuleDefinition] = [
    FddRuleDefinition("CH-001", "CHILLER", "cop_degradation", ["cop"], threshold=3.0, severity="warning", check="cop_degradation", description="COP below threshold"),
    FddRuleDefinition("CH-002", "CHILLER", "low_delta_t", ["chws_temp", "chwr_temp"], threshold=4.0, severity="warning", check="low_delta_t", description="Low chilled water delta-T"),
    FddRuleDefinition("CH-003", "CHILLER", "chws_tracking", ["chws_temp", "chws_setpoint"], threshold=2.0, severity="warning", check="supply_air_temp_deviation", description="CHW supply temperature tracking failure"),
    FddRuleDefinition("CH-004", "CHILLER", "short_cycling", ["compressor_starts_per_hr"], threshold=6, severity="warning", check="short_cycling", description="Possible short cycling"),
]

PUMP_RULES: List[FddRuleDefinition] = [
    FddRuleDefinition("PUMP-001", "PUMP", "pump_command_mismatch", ["pump_command", "pump_status"], threshold=1, severity="warning", check="fan_status_mismatch", description="Pump command/status mismatch"),
    FddRuleDefinition("PUMP-002", "PUMP", "dp_tracking", ["differential_pressure", "dp_setpoint"], threshold=0.5, severity="warning", check="static_pressure_tracking", description="Differential pressure tracking issue"),
]

COOLING_TOWER_RULES: List[FddRuleDefinition] = [
    FddRuleDefinition("CT-001", "COOLING_TOWER", "cw_supply_tracking", ["cw_supply_temp", "cw_supply_setpoint"], threshold=2.0, severity="warning", check="supply_air_temp_deviation", description="CW supply temperature tracking"),
    FddRuleDefinition("CT-002", "COOLING_TOWER", "fan_mismatch", ["fan_command", "fan_status"], threshold=1, severity="warning", check="fan_status_mismatch", description="Cooling tower fan command/status mismatch"),
]

FCU_RULES: List[FddRuleDefinition] = [
    FddRuleDefinition("FCU-001", "FCU", "zone_temp_tracking", ["zone_temp", "zone_setpoint"], threshold=2.0, severity="warning", check="supply_air_temp_deviation", description="Zone temperature tracking failure"),
    FddRuleDefinition("FCU-002", "FCU", "valve_anomaly", ["valve_command", "valve_feedback"], threshold=15, severity="warning", check="oa_damper_mismatch", description="Valve command/feedback mismatch"),
]

VAV_RULES: List[FddRuleDefinition] = [
    FddRuleDefinition("VAV-001", "VAV", "damper_tracking", ["damper_command", "damper_feedback"], threshold=15, severity="warning", check="oa_damper_mismatch", description="VAV damper command/feedback mismatch"),
    FddRuleDefinition("VAV-002", "VAV", "airflow_pressure", ["static_pressure", "static_pressure_setpoint"], threshold=0.3, severity="warning", check="static_pressure_tracking", description="Static pressure tracking issue"),
]

ALL_RULES: List[FddRuleDefinition] = AHU_RULES + CHILLER_RULES + PUMP_RULES + COOLING_TOWER_RULES + FCU_RULES + VAV_RULES


class FddRuleEngine:
    def __init__(self, rules: Optional[List[FddRuleDefinition]] = None) -> None:
        self.rules = rules or ALL_RULES

    def evaluate_equipment(
        self,
        *,
        readings: Dict[str, float],
        point_meta: Dict[str, Dict[str, Any]],
        equipment_id: str,
        equipment_type: str = "AHU",
        tenant_id: Optional[str] = None,
        building_id: Optional[str] = None,
        history_hours: Optional[float] = None,
    ) -> Dict[str, Any]:
        applicable = [r for r in self.rules if r.equipment_type == equipment_type]
        faults: List[Dict[str, Any]] = []
        blocked: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()

        for rule in applicable:
            readiness = validate_fdd_inputs(
                required_keys=rule.required_inputs,
                optional_keys=rule.optional_inputs,
                readings=readings,
                point_meta=point_meta,
                history_available_hours=history_hours,
            )
            if readiness["status"] in ("BLOCKED", "INSUFFICIENT_DATA"):
                blocked.append({"rule_id": rule.rule_id, "readiness": readiness})
                continue

            checker = RULE_CHECKS.get(rule.check)
            if not checker:
                blocked.append({"rule_id": rule.rule_id, "reason": "no_checker"})
                continue

            if checker(readings, rule.threshold):
                conf = min(0.98, rule.min_confidence + readiness["coverage"] * 0.3)
                faults.append({
                    "fault_id": f"{rule.rule_id}:{equipment_id}",
                    "rule_id": rule.rule_id,
                    "tenant_id": tenant_id,
                    "building_id": building_id,
                    "equipment_id": equipment_id,
                    "equipment_type": equipment_type,
                    "detected_at": now,
                    "first_seen": now,
                    "last_seen": now,
                    "severity": rule.severity,
                    "status": "DETECTED",
                    "confidence": round(conf, 2),
                    "data_quality_score": readiness["coverage"],
                    "input_coverage": readiness["coverage"],
                    "evidence": {
                        "check": rule.check,
                        "threshold": rule.threshold,
                        "observed": {k: readings.get(k) for k in rule.required_inputs if k in readings},
                    },
                    "source_points": [point_meta.get(k, {}).get("source_point_id") for k in rule.required_inputs if k in point_meta],
                    "observed_values": {k: readings.get(k) for k in rule.required_inputs},
                    "expected_condition": rule.description,
                    "persistence": rule.persistence_cycles,
                    "reason": rule.description,
                    "recommended_next_check": f"Inspect {equipment_id} — {rule.name}",
                    "readiness": readiness,
                })

        return {"faults": faults, "blocked": blocked, "evaluated_at": now}
