"""Production-path ingest tests."""

from fastapi.testclient import TestClient

from app.main import app


def test_ingest_live_rejects_without_key_in_production(prod_settings):
    client = TestClient(app)
    payload = {
        "building_id": "burj-khalifa-01",
        "timestamp": "2026-06-28T12:00:00Z",
        "hvac": {
            "supply_air_temp": 14.0,
            "return_air_temp": 24.0,
            "delta_t": 10.0,
            "power_kw": 195.0,
            "cop": 3.8,
        },
        "energy": {
            "total_kw": 820.0,
            "hvac_kw": 195.0,
            "lighting_kw": 120.0,
            "other_kw": 505.0,
            "tariff_rate": 0.38,
            "cost_per_hour": 311.6,
        },
        "environment": {
            "temp_c": 23.0,
            "humidity_pct": 48.0,
            "co2_ppm": 600,
            "pm25": 20.0,
        },
        "active_alerts": 0,
        "demo_mode": False,
    }
    response = client.post("/api/v1/ingest/live", json=payload)
    assert response.status_code == 401


def test_ingest_heartbeat_records(prod_settings):
    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/heartbeat",
        json={
            "building_id": "burj-khalifa-01",
            "protocol": "bacnet",
            "data_points": 4,
        },
        headers={"X-API-Key": "test-ingest-key"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
