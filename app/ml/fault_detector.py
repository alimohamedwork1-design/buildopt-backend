"""Rule-based FDD with prerequisites and data quality metadata."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Set

FDD_RULES: List[Dict[str, Any]] = [
    {"id": "FDD-001", "category": "AHU", "check": "supply_air_temp_deviation", "threshold": 2.0, "requires": ["supply_air_temp", "supply_air_setpoint"], "severity": "warning"},
    {"id": "FDD-002", "category": "AHU", "check": "simultaneous_heating_cooling", "threshold": 1, "requires": ["heating_valve_cmd", "cooling_valve_cmd"], "severity": "critical"},
    {"id": "FDD-003", "category": "AHU", "check": "stuck_cooling_valve", "threshold": 95, "requires": ["cooling_valve_cmd"], "severity": "warning"},
    {"id": "FDD-004", "category": "AHU", "check": "fan_status_mismatch", "threshold": 1, "requires": ["fan_command", "fan_status"], "severity": "warning"},
    {"id": "FDD-005", "category": "AHU", "check": "filter_pressure_drop", "threshold": 250, "requires": ["filter_pressure_pa"], "severity": "warning"},
    {"id": "FDD-006", "category": "AHU", "check": "sensor_drift", "threshold": 1, "requires": ["sensor_variance"], "severity": "info"},
    {"id": "FDD-007", "category": "Chiller", "check": "cop_degradation", "threshold": 3.0, "requires": ["cop"], "severity": "warning"},
    {"id": "FDD-008", "category": "Chiller", "check": "low_delta_t", "threshold": 4.0, "requires": ["chws_temp", "chwr_temp"], "severity": "warning"},
    {"id": "FDD-009", "category": "Chiller", "check": "short_cycling", "threshold": 6, "requires": ["compressor_starts_per_hr"], "severity": "warning"},
    {"id": "FDD-010", "category": "Energy", "check": "baseline_deviation", "threshold": 15.0, "requires": ["baseline_deviation_pct"], "severity": "info"},
    {"id": "FDD-011", "category": "BMS", "check": "stuck_sensor", "threshold": 1, "requires": ["sensor_variance"], "severity": "warning"},
]

RULE_CHECKS = {
    "supply_air_temp_deviation": lambda r, t: abs(r.get("supply_air_temp", 0) - r.get("supply_air_setpoint", 22)) > t,
    "simultaneous_heating_cooling": lambda r, t: r.get("heating_valve_cmd", 0) > 10 and r.get("cooling_valve_cmd", 0) > 10,
    "stuck_cooling_valve": lambda r, t: r.get("cooling_valve_cmd", 0) > t,
    "fan_status_mismatch": lambda r, t: r.get("fan_command", 0) > 0.5 and r.get("fan_status", 1) < 0.5,
    "filter_pressure_drop": lambda r, t: r.get("filter_pressure_pa", 0) > t,
    "sensor_drift": lambda r, t: r.get("sensor_variance", 1) == 0,
    "cop_degradation": lambda r, t: r.get("cop", 999) < t,
    "low_delta_t": lambda r, t: abs(r.get("chwr_temp", 0) - r.get("chws_temp", 0)) < t,
    "short_cycling": lambda r, t: r.get("compressor_starts_per_hr", 0) > t,
    "baseline_deviation": lambda r, t: r.get("baseline_deviation_pct", 0) > t,
    "stuck_sensor": lambda r, t: r.get("sensor_variance", 1) == 0,
}


class FaultDetector:
    def __init__(self, demo_mode: bool = True) -> None:
        self.demo_mode = demo_mode
        self.rules = FDD_RULES

    def evaluate(self, readings: Dict[str, float]) -> List[Dict[str, Any]]:
        faults: List[Dict[str, Any]] = []
        not_evaluable: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        present: Set[str] = set(readings.keys())
        required_all = {k for rule in self.rules for k in rule.get("requires", [])}
        missing = [k for k in required_all if k not in present]
        coverage = 1.0 - (len(missing) / max(len(required_all), 1))
        quality_score = round(max(0.0, coverage), 2)

        for rule in self.rules:
            required = rule.get("requires", [rule["check"]])
            if not all(key in present for key in required):
                not_evaluable.append(
                    {
                        "rule_id": rule["id"],
                        "status": "NOT_EVALUABLE",
                        "missing_points": [k for k in required if k not in present],
                    }
                )
                continue

            checker = RULE_CHECKS.get(rule["check"])
            if checker and checker(readings, rule["threshold"]):
                conf = min(0.98, 0.6 + quality_score * 0.35)
                faults.append(self._fault(rule, now, confidence=conf, quality_score=quality_score, input_points=list(present), missing_points=missing))

        if self.demo_mode and not faults:
            from app.services import demo_mode as demo
            return [result.model_dump(mode="json") for result in demo.list_fdd_results()]

        return faults or not_evaluable

    def _fault(
        self,
        rule: Dict[str, Any],
        detected_at: datetime,
        *,
        confidence: float,
        quality_score: float,
        input_points: List[str],
        missing_points: List[str],
    ) -> Dict[str, Any]:
        return {
            "rule_id": rule["id"],
            "category": rule["category"],
            "description": rule["check"],
            "description_ar": "تم اكتشاف عطل في النظام",
            "severity": rule.get("severity", "warning"),
            "confidence": confidence,
            "detected_at": detected_at.isoformat(),
            "status": "OPEN",
            "data_quality_score": quality_score,
            "data_coverage": quality_score,
            "input_points": input_points,
            "missing_points": missing_points,
            "evidence": {"check": rule["check"], "threshold": rule["threshold"]},
            "recommended_action": f"Investigate {rule['category']} — {rule['check']}",
        }
