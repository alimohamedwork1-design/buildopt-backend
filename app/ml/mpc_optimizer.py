from typing import Any, Dict, List


class MPCOptimizer:
    def __init__(self, demo_mode: bool = True) -> None:
        self.demo_mode = demo_mode

    def optimize(self, building_id: str, constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
        max_temp = constraints.get("max_supply_temp", 24.0)
        min_cop = constraints.get("min_cop", 3.2)

        return [
            {
                "action": "reduce_chiller_setpoint",
                "target": "chiller-01",
                "value": 6.5,
                "reason": f"Maintain COP >= {min_cop}",
            },
            {
                "action": "adjust_ahu_setpoint",
                "target": "ahu-01",
                "value": min(max_temp - 2, 22.0),
                "reason": "Optimize peak demand",
            },
            {
                "action": "enable_economizer",
                "target": "ahu-01",
                "value": True,
                "reason": "Lower outdoor enthalpy available",
            },
        ]
