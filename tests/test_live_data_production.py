"""Live data service production-path tests."""

import pytest

from app.services import live_data_service


@pytest.mark.asyncio
async def test_get_live_data_no_silent_demo_fallback(prod_settings, monkeypatch):
    monkeypatch.setattr(live_data_service.live_cache, "get_live", lambda _bid: None)
    monkeypatch.setattr(live_data_service.connection_store, "has_saved_metasys", lambda: False)

    class EmptyInflux:
        def get_latest_snapshot(self, _bid):
            return None

    monkeypatch.setattr(live_data_service, "_influx", lambda **_: EmptyInflux())

    data = await live_data_service.get_live_data("burj-khalifa-01")
    assert data is None
