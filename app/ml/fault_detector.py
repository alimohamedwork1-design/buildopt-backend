from datetime import datetime, timezone
from typing import Any, Dict, List

FDD_RULES: List[Dict[str, Any]] = [
    {"id": "FDD-001", "category": "HVAC", "check": "supply_air_temp_deviation", "threshold": 2.0},
    {"id": "FDD-002", "category": "HVAC", "check": "delta_t_low", "threshold": 5.0},
    {"id": "FDD-003", "category": "HVAC", "check": "discharge_temp_high", "threshold": 18.0},
    {"id": "FDD-004", "category": "HVAC", "check": "economizer_malfunction", "threshold": 1},
    {"id": "FDD-005", "category": "HVAC", "check": "vfd_fault", "threshold": 1},
    {"id": "FDD-006", "category": "HVAC", "check": "coil_fouling", "threshold": 1},
    {"id": "FDD-007", "category": "Chiller", "check": "cop_degradation", "threshold": 3.0},
    {"id": "FDD-008", "category": "Chiller", "check": "condenser_approach_high", "threshold": 4.0},
    {"id": "FDD-009", "category": "Chiller", "check": "refrigerant_leak", "threshold": 1},
    {"id": "FDD-010", "category": "Chiller", "check": "compressor_current_anomaly", "threshold": 1},
    {"id": "FDD-011", "category": "AHU", "check": "filter_pressure_drop", "threshold": 250},
    {"id": "FDD-012", "category": "AHU", "check": "belt_slip", "threshold": 1},
    {"id": "FDD-013", "category": "AHU", "check": "motor_overload", "threshold": 1},
    {"id": "FDD-014", "category": "AHU", "check": "mixed_air_temp_deviation", "threshold": 2.0},
    {"id": "FDD-015", "category": "BMS", "check": "sensor_drift", "threshold": 1},
    {"id": "FDD-016", "category": "BMS", "check": "stuck_sensor", "threshold": 1},
    {"id": "FDD-017", "category": "BMS", "check": "out_of_range", "threshold": 1},
    {"id": "FDD-018", "category": "BMS", "check": "communication_loss", "threshold": 1},
    {"id": "FDD-019", "category": "Energy", "check": "baseline_deviation", "threshold": 15.0},
    {"id": "FDD-020", "category": "Energy", "check": "peak_demand_spike", "threshold": 1},
]


class FaultDetector:
    def __init__(self, demo_mode: bool = True) -> None:
        self.demo_mode = demo_mode
        self.rules = FDD_RULES
        self._model = None
        if not demo_mode:
            try:
                import xgboost as xgb

                self._model = xgb.XGBClassifier()
            except Exception:
                self._model = None

    def evaluate(self, readings: Dict[str, float]) -> List[Dict[str, Any]]:
        faults: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        if readings.get("cop", 4.0) < 3.0:
            faults.append(self._fault("FDD-007", "Chiller", "COP degradation below 3.0", now))
        if readings.get("filter_pressure_pa", 100) > 250:
            faults.append(self._fault("FDD-011", "AHU", "Filter pressure drop exceeds 250 Pa", now))
        if readings.get("supply_air_temp_deviation", 0) > 2.0:
            faults.append(self._fault("FDD-001", "HVAC", "Supply air temp deviation > 2°C", now))
        if readings.get("baseline_deviation_pct", 0) > 15:
            faults.append(self._fault("FDD-019", "Energy", "Baseline deviation > 15%", now))
        if readings.get("power_factor", 0.9) < 0.85:
            faults.append(self._fault("FDD-021", "Energy", "Power factor below 0.85", now))

        if self.demo_mode and not faults:
            from app.services import demo_mode as demo

            return [result.model_dump(mode="json") for result in demo.list_fdd_results()]

        return faults

    def _fault(self, rule_id: str, category: str, description: str, detected_at: datetime) -> Dict[str, Any]:
        return {
            "rule_id": rule_id,
            "category": category,
            "description": description,
            "description_ar": "تم اكتشاف عطل في النظام",
            "severity": "warning",
            "confidence": 0.87,
            "detected_at": detected_at.isoformat(),
        }
