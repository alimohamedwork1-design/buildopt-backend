"""Site-history energy forecaster with explicit validation metadata.

This is deliberately not called an LSTM. It trains a small gradient-boosting model on
recent site history and refuses to forecast when history is insufficient.
"""

from __future__ import annotations

import math
from datetime import timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from app.models.user_context import UserContext
from app.services import live_data_service

MIN_OBSERVATIONS = 48
TARGET_HISTORY_HOURS = 168
MAX_HORIZON_HOURS = 72


def _cyclic(value: float, period: float) -> Tuple[float, float]:
    angle = 2.0 * math.pi * value / period
    return math.sin(angle), math.cos(angle)


def _features(ts, values: Sequence[float]) -> List[float]:
    hour_sin, hour_cos = _cyclic(float(ts.hour), 24.0)
    dow_sin, dow_cos = _cyclic(float(ts.weekday()), 7.0)
    lag1 = float(values[-1])
    lag24 = float(values[-24]) if len(values) >= 24 else lag1
    rolling6 = float(np.mean(values[-6:]))
    rolling24 = float(np.mean(values[-24:])) if len(values) >= 24 else float(np.mean(values))
    return [hour_sin, hour_cos, dow_sin, dow_cos, lag1, lag24, rolling6, rolling24]


class HistoryForecaster:
    model_name = "gradient_boosting_autoregressive"
    model_version = "1.0.0-pilot"

    def forecast(
        self,
        building_id: str,
        horizon_hours: int = 24,
        user: Optional[UserContext] = None,
    ) -> Dict[str, Any]:
        horizon = max(1, min(int(horizon_hours), MAX_HORIZON_HOURS))
        # Forecasting is a live-data operation. If called internally without a user,
        # force an anonymous LIVE context so a global DEMO_MODE cannot leak simulated
        # history into a live forecast path.
        history_user = user or UserContext.anonymous_live()
        metrics = live_data_service.get_building_metrics(building_id, "7d", user=history_user)
        if metrics is None:
            return self._unavailable(building_id, horizon, "NO_HISTORY", 0)

        points = sorted(
            [p for p in metrics.metrics if p.metric == "total_kw"],
            key=lambda p: p.timestamp,
        )
        if len(points) < MIN_OBSERVATIONS:
            return self._unavailable(building_id, horizon, "INSUFFICIENT_HISTORY", len(points))

        timestamps = [p.timestamp for p in points]
        values = [float(p.value) for p in points]
        x_rows: List[List[float]] = []
        y_rows: List[float] = []

        warmup = min(24, max(6, len(values) // 4))
        for idx in range(warmup, len(values)):
            x_rows.append(_features(timestamps[idx], values[:idx]))
            y_rows.append(values[idx])

        if len(x_rows) < 24:
            return self._unavailable(building_id, horizon, "INSUFFICIENT_TRAINING_ROWS", len(points))

        x = np.asarray(x_rows, dtype=float)
        y = np.asarray(y_rows, dtype=float)
        holdout = max(12, int(round(len(y) * 0.2)))
        holdout = min(holdout, max(1, len(y) // 3))
        split = len(y) - holdout
        if split < 12:
            return self._unavailable(building_id, horizon, "INSUFFICIENT_TRAINING_ROWS", len(points))

        model = GradientBoostingRegressor(
            random_state=42,
            n_estimators=120,
            learning_rate=0.04,
            max_depth=2,
            loss="huber",
        )
        model.fit(x[:split], y[:split])
        validation_pred = model.predict(x[split:])
        mae = float(mean_absolute_error(y[split:], validation_pred))
        mean_kw = float(max(np.mean(np.abs(y[split:])), 1.0))
        normalized_mae = mae / mean_kw
        coverage = min(1.0, len(points) / TARGET_HISTORY_HOURS)
        confidence = max(0.25, min(0.97, (1.0 - normalized_mae) * (0.65 + 0.35 * coverage)))

        model.fit(x, y)
        generated_values = list(values)
        ts = timestamps[-1]
        forecast_rows: List[Dict[str, Any]] = []
        for _ in range(horizon):
            ts = ts + timedelta(hours=1)
            feature_row = np.asarray([_features(ts, generated_values)], dtype=float)
            predicted = max(0.0, float(model.predict(feature_row)[0]))
            generated_values.append(predicted)
            forecast_rows.append(
                {
                    "timestamp": ts.isoformat(),
                    "predicted_kw": round(predicted, 2),
                    "confidence": round(confidence, 3),
                }
            )

        return {
            "building_id": building_id,
            "horizon_hours": horizon,
            "forecast": forecast_rows,
            "available": True,
            "demo_mode": False,
            "method": self.model_name,
            "model_version": self.model_version,
            "training_observations": len(points),
            "history_coverage_pct": round(coverage * 100.0, 1),
            "validation": {
                "holdout_points": holdout,
                "mae_kw": round(mae, 2),
                "normalized_mae": round(normalized_mae, 4),
            },
        }

    def _unavailable(self, building_id: str, horizon: int, reason: str, observations: int) -> Dict[str, Any]:
        return {
            "building_id": building_id,
            "horizon_hours": horizon,
            "forecast": [],
            "available": False,
            "demo_mode": False,
            "method": self.model_name,
            "model_version": self.model_version,
            "reason": reason,
            "training_observations": observations,
            "minimum_observations": MIN_OBSERVATIONS,
        }
