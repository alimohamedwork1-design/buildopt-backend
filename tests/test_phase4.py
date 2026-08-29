"""Phase 4 — semantic mapping V2, registry data health, gateway tokens, influx history."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.gateway_token_store import GatewayTokenStore, reset_gateway_token_store
from app.services.influx_client import InfluxService, _flux_safe_tag
from app.services.semantic_mapping_service import (
    approve_registry_mapping,
    build_collection_config,
    suggest_registry_mappings,
)
from app.services.telemetry_store import TelemetryStore, reset_telemetry_store


@pytest.fixture(autouse=True)
def fresh_store():
    store = TelemetryStore(":memory:")
    reset_telemetry_store(store)
    reset_gateway_token_store(GatewayTokenStore(store))
    yield store
    reset_telemetry_store(None)
    reset_gateway_token_store(None)


@pytest.fixture
def client():
    return TestClient(app)


def _seed_point(
    store: TelemetryStore,
    *,
    name: str,
    source_id: str,
    building_id: str = "b1",
    tenant_id: str = "tenant-a",
    gateway_id: str = "gw-1",
) -> dict:
    store.register_gateway(
        gateway_id=gateway_id, tenant_id=tenant_id, building_id=building_id, connector_id="metasys"
    )
    return store.upsert_raw_point(
        {
            "tenant_id": tenant_id,
            "building_id": building_id,
            "gateway_id": gateway_id,
            "connector_id": "metasys",
            "source": "metasys",
            "source_point_id": source_id,
            "source_name": name,
            "raw_unit": "degC",
        }
    )


def test_semantic_suggestions_do_not_modify_registry(fresh_store):
    p = _seed_point(fresh_store, name="AHU1 Supply Air Temp", source_id="obj-sat")
    original_id = p["source_point_id"]
    points, _ = fresh_store.list_points(building_id="b1")
    suggest_registry_mappings(points, merge=False)
    unchanged = fresh_store.get_point(p["id"])
    assert unchanged["source_point_id"] == original_id
    assert (unchanged.get("metadata") or {}).get("mapping_status") != "APPROVED"


def test_collection_config_zero_and_mixed_mappings(fresh_store):
    p1 = _seed_point(fresh_store, name="SAT", source_id="obj-sat")
    _seed_point(fresh_store, name="RAT", source_id="obj-rat")
    points, _ = fresh_store.list_points(building_id="b1")
    empty = build_collection_config(points, building_id="b1")
    assert empty["mapping"] == {}

    approve_registry_mapping(
        fresh_store,
        building_id="b1",
        semantic_key="supply_air_temp",
        source_point_id="obj-sat",
    )
    points, _ = fresh_store.list_points(building_id="b1")
    partial = build_collection_config(points, building_id="b1")
    assert partial["mapping"] == {"supply_air_temp": "obj-sat"}
    assert len(partial["points"]) == 1
    assert all(pt["source_point_id"] != "obj-rat" for pt in partial["points"])


def test_collection_config_wrong_building(fresh_store):
    _seed_point(fresh_store, name="SAT", source_id="obj-sat", building_id="b2")
    points, _ = fresh_store.list_points(building_id="b1")
    config = build_collection_config(points, building_id="b1")
    assert config["mapping"] == {}


def test_approve_rejects_low_confidence(fresh_store):
    _seed_point(fresh_store, name="SAT", source_id="obj-sat")
    with pytest.raises(ValueError, match="confidence_too_low"):
        approve_registry_mapping(
            fresh_store,
            building_id="b1",
            semantic_key="supply_air_temp",
            source_point_id="obj-sat",
            confidence=0.5,
        )


def test_gateway_token_security_lifecycle(fresh_store, client, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "master-key")
    fresh_store.register_gateway(
        gateway_id="gw-edge", tenant_id="t1", building_id="b1", connector_id="metasys"
    )
    token_store = GatewayTokenStore(fresh_store)
    issued = token_store.issue(gateway_id="gw-edge", label="edge")
    assert issued["token"].startswith("bo_gw_gw-edge_")
    assert len(issued["token"]) > 20

    listed = token_store.list_for_gateway("gw-edge")
    assert listed[0]["token_id"] == issued["token_id"]
    assert "token" not in listed[0]
    assert "token_hash" not in listed[0]

    res_issue = client.post(
        "/api/v1/gateways/gw-edge/tokens",
        json={"label": "edge2"},
        headers={"X-API-Key": issued["token"]},
    )
    assert res_issue.status_code == 401

    res_list = client.get(
        "/api/v1/gateways/gw-edge/tokens",
        headers={"X-API-Key": issued["token"]},
    )
    assert res_list.status_code == 401

    res_ingest = client.post(
        "/api/v1/telemetry/batch",
        json={
            "gateway_id": "gw-other",
            "tenant_id": "t1",
            "building_id": "b1",
            "readings": [],
        },
        headers={"X-API-Key": issued["token"]},
    )
    assert res_ingest.status_code == 403

    res_ok = client.post(
        "/api/v1/telemetry/batch",
        json={
            "gateway_id": "gw-edge",
            "tenant_id": "t1",
            "building_id": "b1",
            "readings": [],
        },
        headers={"X-API-Key": issued["token"]},
    )
    assert res_ok.status_code == 200

    token_store.revoke(issued["token_id"])
    res_revoked = client.post(
        "/api/v1/telemetry/batch",
        json={
            "gateway_id": "gw-edge",
            "tenant_id": "t1",
            "building_id": "b1",
            "readings": [],
        },
        headers={"X-API-Key": issued["token"]},
    )
    assert res_revoked.status_code == 401


def test_gateway_collection_config_endpoint(fresh_store, client, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "master-key")
    _seed_point(fresh_store, name="SAT", source_id="obj-sat")
    approve_registry_mapping(
        fresh_store,
        building_id="b1",
        semantic_key="supply_air_temp",
        source_point_id="obj-sat",
    )
    token_store = GatewayTokenStore(fresh_store)
    issued = token_store.issue(gateway_id="gw-1")
    res = client.get(
        "/api/v1/gateways/gw-1/collection-config",
        headers={"X-API-Key": issued["token"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mapping"]["supply_air_temp"] == "obj-sat"


def test_registry_data_health_offline_without_value(fresh_store):
    from app.services.data_health_engine import registry_building_data_health

    _seed_point(fresh_store, name="SAT", source_id="obj-1")
    points = fresh_store.list_building_current("b1")
    health = registry_building_data_health(points)
    assert health["points"][0]["status"] in ("OFFLINE", "UNKNOWN", "MISSING", "NO_DATA", "INVALID")
    assert health["building_summary"]["availability_pct"] < 100


def test_influx_flux_injection_blocked():
    svc = InfluxService("http://localhost:8086", "", "org", "bucket", demo_mode=True)
    with pytest.raises(ValueError):
        _flux_safe_tag('b1" |> drop()')
    assert svc.query_telemetry_point_history(
        point_id='x" |> drop()',
        building_id="b1",
        hours=24,
    ) == []


def test_building_telemetry_history_endpoint(client, fresh_store, monkeypatch):
    _seed_point(fresh_store, name="SAT", source_id="obj-1")

    class FakeInflux:
        def infrastructure_state(self):
            return {"status": "connected", "persistence": True}

        def query_building_telemetry_history(self, building_id, **kwargs):
            return [{"timestamp": "2026-08-29T10:00:00Z", "value": 12.3, "point_id": "p1"}]

    monkeypatch.setattr("app.api.buildings.get_influx_service", lambda: FakeInflux())
    res = client.get("/api/v1/buildings/b1/telemetry/history?hours=24")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["series"][0]["value"] == 12.3

    bad = client.get("/api/v1/buildings/b1/telemetry/history?hours=999")
    assert bad.status_code == 422
