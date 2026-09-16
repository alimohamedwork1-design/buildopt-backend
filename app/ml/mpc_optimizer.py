"""Bounded shadow-mode optimization advisor.

This is not a mathematical MPC solver yet: there is no calibrated plant model, prediction
horizon, or objective-function solve in this class. It therefore emits only operator-review
candidates and never claims verified savings or performs writeback.
"""

from __future__ import annotations

from typing import Any, Dict, List


class MPCOptimizer:
    """Compatibility name for the current bounded rule advisor."""

    engine_mode = "bounded_rule_advisor_shadow_only"
    model_version = "1.0.0-pilot"

    def __init__(self, demo_mode: bool = True) -> None:
        self.demo_mode = demo_mode

    def optimize(self, building_id: str, constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
        min_cop = float(constraints.get("min_cop", 3.2))
        min_supply = float(constraints.get("min_supply_temp", 12.0))
        max_supply = float(constraints.get("max_supply_temp", 24.0))
        current_cop = constraints.get("current_cop")
        current_supply = constraints.get("current_supply_temp")
        outdoor_enthalpy = constraints.get("outdoor_enthalpy")
        return_enthalpy = constraints.get("return_enthalpy")
        economizer_available = bool(constraints.get("economizer_available", False))

        recommendations: List[Dict[str, Any]] = []

        if isinstance(current_cop, (int, float)) and float(current_cop) < min_cop:
            recommendations.append({
                "action": "review_chiller_staging",
                "target": "chiller_plant",
                "value": None,
                "reason": f"Observed COP {float(current_cop):.2f} is below configured minimum {min_cop:.2f}",
                "candidate_only": True,
                "writeback_allowed": False,
                "engine_mode": self.engine_mode,
            })

        if isinstance(current_supply, (int, float)):
            current_supply_f = float(current_supply)
            bounded_target = min(max(current_supply_f, min_supply), max_supply)
            if bounded_target != current_supply_f:
                recommendations.append({
                    "action": "review_supply_temperature_setpoint",
                    "target": "ahu_supply_temperature",
                    "value": round(bounded_target, 2),
                    "reason": f"Current value is outside configured bounds [{min_supply}, {max_supply}]",
                    "candidate_only": True,
                    "writeback_allowed": False,
                    "engine_mode": self.engine_mode,
                })

        if (
            economizer_available
            and isinstance(outdoor_enthalpy, (int, float))
            and isinstance(return_enthalpy, (int, float))
            and float(outdoor_enthalpy) + 1.0 < float(return_enthalpy)
        ):
            recommendations.append({
                "action": "review_economizer_enable",
                "target": "ahu_economizer",
                "value": True,
                "reason": "Outdoor enthalpy is lower than return-air enthalpy by the configured margin",
                "candidate_only": True,
                "writeback_allowed": False,
                "engine_mode": self.engine_mode,
            })

        if not recommendations:
            recommendations.append({
                "action": "collect_operating_state",
                "target": building_id,
                "value": None,
                "reason": "No defensible optimization candidate can be produced from the supplied state/constraints",
                "candidate_only": True,
                "writeback_allowed": False,
                "engine_mode": self.engine_mode,
            })

        return recommendations
