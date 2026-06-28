from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ingest_status():
    r = client.get("/api/v1/ingest/status")
    assert r.status_code == 200
    assert "demo_mode" in r.json()


def test_ingest_live_without_key_when_no_key_configured():
    payload = {
        "building_id": "burj-khalifa-01",
        "timestamp": "2026-06-28T12:00:00Z",
        "hvac": {
            "supply_air_temp": 14.0,
            "return_air_temp": 24.0,
            "delta_t": 10.0,
            "power_kw": 200.0,
            "cop": 3.7,
        },
        "energy": {
            "total_kw": 850.0,
            "hvac_kw": 200.0,
            "lighting_kw": 120.0,
            "other_kw": 530.0,
            "tariff_rate": 0.38,
            "cost_per_hour": 323.0,
        },
        "environment": {
            "temp_c": 23.0,
            "humidity_pct": 50.0,
            "co2_ppm": 650,
            "pm25": 18.0,
        },
        "active_alerts": 1,
        "demo_mode": False,
    }
    r = client.post("/api/v1/ingest/live", json=payload)
    assert r.status_code == 200
    assert r.json()["demo_mode"] is False


def test_live_after_ingest():
    r = client.get("/api/v1/buildings/burj-khalifa-01/live")
    assert r.status_code == 200
    assert r.json()["hvac"]["power_kw"] == 200.0
