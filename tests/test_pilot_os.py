from __future__ import annotations

import pytest

from app.models.user_context import UserContext
from app.services.pilot_os_service import build_pilot_summary, evaluate_rule_packs, model_registry
from app.services.telemetry_store import get_telemetry_store


def test_rule_pack_readiness_is_evidence_based():
    packs = evaluate_rule_packs({"total_kw", "supply_air_temp", "return_air_temp"})
    by_id = {p["id"]: p for p in packs}
    assert by_id["energy_metering"]["ready"] is True
    assert by_id["ahu_thermal"]["ready"] is True
    assert by_id["hvac_efficiency"]["ready"] is False
    assert "hvac_power_kw" in by_id["hvac_efficiency"]["missing_required"]


def test_model_registry_does_not_claim_autonomous_writeback():
    models = model_registry()
    assert models
    assert all(m["writeback"] is False for m in models)
    optimization = next(m for m in models if m["id"] == "optimization_shadow_v1")
    assert optimization["maturity"] == "heuristic"
    assert optimization["implementation"] == "bounded_rule_advisor"


@pytest.mark.asyncio
async def test_empty_live_pilot_is_blocked_not_fabricated(monkeypatch):
    user = UserContext(
        user_id="u-live",
        account_mode="live",
        authenticated=True,
        access_level="read_write",
        roles=["facility_manager"],
        building_ids=["b-live"],
    )

    async def no_connection(_building_id: str):
        return None

    monkeypatch.setattr("app.services.pilot_os_service.get_connection", no_connection)
    monkeypatch.setattr("app.services.pilot_os_service.live_data_service.get_building_metrics", lambda *args, **kwargs: None)

    summary = await build_pilot_summary(user, "b-live")
    assert summary["state"] == "PILOT_BLOCKED"
    assert summary["connections"]["connected"] is False
    assert summary["points"]["total"] == 0
    assert summary["operations"]["verified_savings_aed"] == 0
    assert summary["safety"]["automatic_writeback"] is False
    assert summary["notifications"]["state"] == "NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_mapping_progress_uses_approved_registry_points(monkeypatch):
    user = UserContext(
        user_id="tenant-1",
        account_mode="live",
        authenticated=True,
        access_level="read_write",
        roles=["facility_manager"],
        building_ids=["b1"],
    )
    store = get_telemetry_store()
    gateway = "gw1"
    for idx, semantic in enumerate(("total_kw", "supply_air_temp", "return_air_temp")):
        point = store.upsert_raw_point(
            {
                "tenant_id": "tenant-1",
                "building_id": "b1",
                "gateway_id": gateway,
                "connector_id": "metasys",
                "source": "metasys",
                "source_point_id": f"p{idx}",
                "source_name": semantic,
                "raw_unit": "kW" if semantic == "total_kw" else "degC",
            }
        )
        meta = dict(point.get("metadata") or {})
        meta.update({"mapping_status": "APPROVED", "semantic_key": semantic, "confidence": 0.99})
        store.update_point_metadata(point["id"], meta)

    async def connected(_building_id: str):
        return {"status": "connected", "protocol": "metasys"}

    monkeypatch.setattr("app.services.pilot_os_service.get_connection", connected)
    monkeypatch.setattr("app.services.pilot_os_service.live_data_service.get_building_metrics", lambda *args, **kwargs: None)

    summary = await build_pilot_summary(user, "b1")
    assert summary["points"]["mapping_pct"] == 100.0
    assert summary["connections"]["connected"] is True
    ahu_pack = next(p for p in summary["rule_packs"] if p["id"] == "ahu_thermal")
    assert ahu_pack["ready"] is True
