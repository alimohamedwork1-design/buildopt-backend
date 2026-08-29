"""Rule-based FDD with prerequisite checks."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

FDD_RULES: List[Dict[str, Any]] = [
    {"id": "FDD-001", "category": "HVAC", "check": "supply_air_temp_deviation", "threshold": 2.0, "requires": ["supply_air_temp_deviation"]},
    {"id": "FDD-007", "category": "Chiller", "check": "cop_degradation", "threshold": 3.0, "requires": ["cop"]},
    {"id": "FDD-011", "category": "AHU", "check": "filter_pressure_drop", "threshold": 250, "requires": ["filter_pressure_pa"]},
    {"id": "FDD-016", "category": "BMS", "check": "stuck_sensor", "threshold": 1, "requires": ["sensor_variance"]},
    {"id": "FDD-019", "category": "Energy", "check": "baseline_deviation", "threshold": 15.0, "requires": ["baseline_deviation_pct"]},
    {"id": "FDD-022", "category": "Refrigeration", "check": "high_superheat", "threshold": 10.0, "requires": ["superheat_k"]},
    {"id": "FDD-025", "category": "Refrigeration", "check": "nh3_leak", "threshold": 25.0, "requires": ["nh3_ppm"]},
]

RULE_CHECKS = {
    "cop_degradation": lambda r, t: r.get("cop", 999) < t,
    "filter_pressure_drop": lambda r, t: r.get("filter_pressure_pa", 0) > t,
    "supply_air_temp_deviation": lambda r, t: r.get("supply_air_temp_deviation", 0) > t,
    "baseline_deviation": lambda r, t: r.get("baseline_deviation_pct", 0) > t,
    "high_superheat": lambda r, t: r.get("superheat_k", r.get("superheat", 0)) > t,
    "nh3_leak": lambda r, t: r.get("nh3_ppm", 0) > t,
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
                faults.append(self._fault(rule["id"], rule["category"], rule["check"], now))

        if self.demo_mode and not faults:
            from app.services import demo_mode as demo

            return [result.model_dump(mode="json") for result in demo.list_fdd_results()]

        if not_evaluable and not faults:
            return not_evaluable
        return faults

    def _fault(self, rule_id: str, category: str, description: str, detected_at: datetime, severity: str = "warning") -> Dict[str, Any]:
        return {
            "rule_id": rule_id,
            "category": category,
            "description": description,
            "description_ar": "تم اكتشاف عطل في النظام",
            "severity": severity,
            "confidence": 0.87,
            "detected_at": detected_at.isoformat(),
            "status": "OPEN",
        }
