"""Data integrity tests — live mode must not return simulated telemetry."""

import pytest

from app.models.user_context import UserContext
from app.services import live_data_service, module_data_service


@pytest.mark.asyncio
async def test_module_data_live_empty_without_telemetry(prod_settings, monkeypatch):
    live_user = UserContext(
        user_id="u1",
        account_mode="live",
        authenticated=True,
        building_ids=["b1"],
        enabled_modules={"overview"},
    )

    async def _no_live(_bid, user=None):
        return None

    monkeypatch.setattr(live_data_service, "get_live_data", _no_live)

    payload = await module_data_service.get_module_data("overview", "b1", user=live_user)
    assert payload["empty_state"] is True
    assert payload["demo_mode"] is False
    assert payload["metric_cards"] == []
    assert "random" not in str(payload).lower()


@pytest.mark.asyncio
async def test_list_alerts_live_returns_empty_not_demo(prod_settings):
    user = UserContext(user_id="u1", account_mode="live", authenticated=True)
    alerts = live_data_service.list_alerts(user=user)
    assert alerts == []


def test_list_equipment_live_returns_empty_not_demo(prod_settings):
    user = UserContext(user_id="u1", account_mode="live", authenticated=True)
    assert live_data_service.list_equipment("b1", user=user) == []
