"""Prevent unsupported measured savings, billing and forecast claims."""

from app.services import live_data_service


def test_live_savings_without_verified_baseline_returns_none(monkeypatch):
    monkeypatch.setattr(live_data_service, "allows_simulated_telemetry", lambda user: False)
    assert live_data_service.get_energy_savings("test-building") is None


def test_live_forecast_does_not_fabricate_points(monkeypatch):
    monkeypatch.setattr(live_data_service, "allows_simulated_telemetry", lambda user: False)
    forecast = live_data_service.get_energy_forecast("test-building")
    assert forecast.forecast == []
    assert forecast.demo_mode is False


def test_live_tariff_requires_real_interval_consumption(monkeypatch):
    monkeypatch.setattr(live_data_service, "allows_simulated_telemetry", lambda user: False)
    monkeypatch.setattr(live_data_service.live_cache, "get_dewa_tariff", lambda: None)
    monkeypatch.setattr(live_data_service.live_cache, "get_live", lambda building_id: None)
    class EmptyInflux:
        def get_latest_snapshot(self, building_id):
            return None
    monkeypatch.setattr(live_data_service, "_influx", lambda **kwargs: EmptyInflux())
    assert live_data_service.get_dewa_tariff("test-building") is None
