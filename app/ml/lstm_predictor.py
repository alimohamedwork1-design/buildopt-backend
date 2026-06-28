from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.services import demo_mode


class LSTMPredictor:
    def __init__(self, demo_mode: bool = True) -> None:
        self.demo_mode = demo_mode
        self._model = None

    def forecast(self, building_id: str, horizon_hours: int = 24) -> Dict[str, Any]:
        if self.demo_mode:
            return demo_mode.get_energy_forecast(building_id, horizon_hours).model_dump(mode="json")

        now = datetime.now(timezone.utc)
        base = 820.0
        forecast = []
        for hour in range(1, horizon_hours + 1):
            ts = now + timedelta(hours=hour)
            predicted = base + (hour % 6) * 12
            forecast.append(
                {
                    "timestamp": ts.isoformat(),
                    "predicted_kw": predicted,
                    "confidence": 0.88,
                }
            )
        return {
            "building_id": building_id,
            "horizon_hours": horizon_hours,
            "forecast": forecast,
            "demo_mode": False,
        }
