from typing import Any, Dict, List

from app.services import demo_mode


class LSTMPredictor:
    def __init__(self, demo_mode: bool = True) -> None:
        self.demo_mode = demo_mode
        self._model = None

    def forecast(self, building_id: str, horizon_hours: int = 24) -> Dict[str, Any]:
        if self.demo_mode:
            return demo_mode.get_energy_forecast(building_id, horizon_hours).model_dump(mode="json")

        return {
            "building_id": building_id,
            "horizon_hours": horizon_hours,
            "forecast": [],
            "demo_mode": False,
            "state": "MODEL_NOT_DEPLOYED",
            "model_version": None,
            "limitations": [
                "No trained LSTM artifact is deployed for live production use.",
                "Use the historical baseline forecast endpoint until validation is complete.",
            ],
        }
