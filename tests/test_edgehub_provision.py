"""BuildOpt EdgeHub simulation provisioning and mode reporting contract."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.config import get_settings
from app.services.edge_heartbeat_store import edge_heartbeat_store
from app.services.gateway_token_store import reset_gateway_token_store
from app.services.telemetry_store import get_telemetry_store


def _headers():
    return {"X-API-Key": "edgehub-admin-test"}


def _body():
    return {
        "tenant_id": "tenant-demo-001",
        "building_id": "building-demo-001",
        "connector_id": "modbus",
        "confirm_test_building": True,
        "expires_in_days": 7,
    }


def test_provision_requires_master_key_even_in_dev(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("INGEST_API_KEY", raising=False)
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.post("/api/v1/gateways/sim-unit-001/provision", json=_body())
    assert response.status_code == 503
    get_settings.cache_clear()


def test_scoped_provision_rejects_bad_credentials(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("INGEST_API_KEY", "edgehub-admin-test")
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.post("/api/v1/gateways/sim-unit-001/provision", json=_body(),
                           headers={"X-API-Key": "wrong"})
    assert response.status_code == 401
    get_settings.cache_clear()


def test_provision_binds_scope_and_reports_mode(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("INGEST_API_KEY", "edgehub-admin-test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-edgehub")
    get_settings.cache_clear()
    reset_gateway_token_store()
    client = TestClient(app)
    denial = client.post("/api/v1/gateways/unsafe-device/provision", json=_body(), headers=_headers())
    assert denial.status_code == 400
    response = client.post("/api/v1/gateways/sim-unit-001/provision", json=_body(), headers=_headers())
    assert response.status_code == 200, response.text
    body = response.json()
    token = body["token"]
    assert token.startswith("bo_gw_")
    assert body["simulation_only"] is True
    registered = get_telemetry_store().get_gateway("sim-unit-001")
    assert registered["building_id"] == "building-demo-001"

    conflict = client.post(
        "/api/v1/gateways/sim-unit-001/provision",
        json={**_body(), "tenant_id": "another-tenant"},
        headers=_headers(),
    )
    assert conflict.status_code == 409

    heartbeat = client.post("/api/v1/gateways/heartbeat", json={
        "gateway_id": "sim-unit-001", "building_id": "building-demo-001",
        "tenant_id": "tenant-demo-001", "connector_id": "modbus",
        "connector_status": "SIMULATED", "operating_mode": "hybrid_4g",
        "edge_clock_at": datetime.now(timezone.utc).isoformat(),
    }, headers={"X-API-Key": token})
    assert heartbeat.status_code == 200, heartbeat.text
    record = edge_heartbeat_store.get_gateway("sim-unit-001")
    assert record["operating_mode"] == "hybrid_4g"
    assert record["connector_status"] == "SIMULATED"

    spoof = client.post("/api/v1/gateways/heartbeat", json={
        "gateway_id": "sim-unit-001", "building_id": "another-building",
        "tenant_id": "tenant-demo-001", "connector_id": "modbus",
    }, headers={"X-API-Key": token})
    assert spoof.status_code == 403
    get_settings.cache_clear()
    reset_gateway_token_store()
