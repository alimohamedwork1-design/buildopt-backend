"""Backward-compatible forecast adapter.

Historically this class was called `LSTMPredictor`, but no persisted/trained LSTM artifact
was loaded. The implementation now delegates to the validated site-history forecaster and
must not be presented as an LSTM in product/UI copy.
"""

from typing import Any, Dict, Optional

from app.ml.history_forecaster import HistoryForecaster
from app.models.user_context import UserContext
from app.services import demo_mode


class LSTMPredictor:
    """Compatibility wrapper; deprecated name retained to avoid breaking callers."""

    def __init__(self, demo_mode: bool = True) -> None:
        self.demo_mode = demo_mode
        self._forecaster = HistoryForecaster()

    def forecast(
        self,
        building_id: str,
        horizon_hours: int = 24,
        user: Optional[UserContext] = None,
    ) -> Dict[str, Any]:
        if self.demo_mode:
            payload = demo_mode.get_energy_forecast(building_id, horizon_hours).model_dump(mode="json")
            payload.update({
                "available": True,
                "method": "demo_simulation",
                "model_version": "demo",
            })
            return payload
        return self._forecaster.forecast(building_id, horizon_hours, user=user)
