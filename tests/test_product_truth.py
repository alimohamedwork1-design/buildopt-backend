from datetime import datetime, timedelta, timezone

import pytest

from app.data.modules_registry import get_module_capability
from app.ml.history_forecaster import HistoryForecaster
from app.models.schemas import BuildingMetrics, MetricPoint
from app.models.user_context import UserContext
from app.services import live_data_service
from app.services.module_data_service import get_module_data


def test_module_capability_registry_is_conservative():
    assert get_module_capability("telemetry")["maturity"] == "production"
    assert get_module_capability("optimization")["maturity"] == "heuristic"
    assert get_module_capability("quantum-optimizer")["maturity"] == "concept"
    assert get_module_capability("white-label")["maturity"] == "simulated"


@pytest.mark.asyncio
async def test_concept_module_cannot_masquerade_as_live():
    user = UserContext(
        user_id="u1",
        account_mode="live",
        building_ids=["building-01"],
        enabled_modules={"quantum-optimizer"},
        authenticated=True,
    )
    payload = await get_module_data("quantum-optimizer", "building-01", user=user)
    assert payload["empty_state"] is True
    assert payload["reason"] == "CAPABILITY_NOT_IMPLEMENTED"
    assert payload["demo_mode"] is False
    assert payload["capability"]["maturity"] == "concept"
    assert payload["metric_cards"] == []
    assert payload["recommendations"] == []


def _history(hours: int) -> BuildingMetrics:
    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    points = []
    for i in range(hours):
        ts = start + timedelta(hours=i)
        # Repeatable daily load shape with a small weekly drift.
        base = 600 + (ts.hour - 12) ** 2 * 1.8 + (ts.weekday() * 3)
        points.append(MetricPoint(timestamp=ts, value=float(base), metric="total_kw"))
    return BuildingMetrics(building_id="building-01", period="7d", metrics=points)


def test_history_forecaster_trains_and_validates(monkeypatch):
    monkeypatch.setattr(live_data_service, "get_building_metrics", lambda *_args, **_kwargs: _history(120))
    result = HistoryForecaster().forecast("building-01", 12)
    assert result["available"] is True
    assert result["method"] == "gradient_boosting_autoregressive"
    assert result["training_observations"] == 120
    assert len(result["forecast"]) == 12
    assert result["validation"]["mae_kw"] >= 0
    assert all(0.0 < row["confidence"] <= 1.0 for row in result["forecast"])


def test_history_forecaster_refuses_short_history(monkeypatch):
    monkeypatch.setattr(live_data_service, "get_building_metrics", lambda *_args, **_kwargs: _history(24))
    result = HistoryForecaster().forecast("building-01", 12)
    assert result["available"] is False
    assert result["reason"] == "INSUFFICIENT_HISTORY"
    assert result["forecast"] == []
