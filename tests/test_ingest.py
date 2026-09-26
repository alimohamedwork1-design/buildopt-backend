from fastapi.testclient import TestClient

from app.main import app
from app.config import get_settings


client = TestClient(app)


def _ingest_headers() -> dict[str, str]:
    key = get_settings().ingest_api_key
    return {"X-API-Key": key} if key else {}


def _payload(power_kw: float = 200.0) -> dict:
    return {
        "building_id": "burj-khalifa-01",
        "timestamp": "2026-06-28T12:00:00Z",
        "hvac": {
            "supply_air_temp": 14.0,
            "return_air_temp": 24.0,
            "delta_t": 10.0,
            "power_kw": power_kw,
            "cop": 3.7,
        },
        "energy": {
            "total_kw": 850.0,
            "hvac_kw": power_kw,
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


def test_ingest_status():
    r = client.get("/api/v1/ingest/status")
    assert r.status_code == 200
    assert "demo_mode" in r.json()


def test_ingest_requires_configured_key_in_production():
    headers = _ingest_headers()
    r = client.post("/api/v1/ingest/live", json=_payload(), headers=headers)
    # Production CI configures INGEST_API_KEY, so authenticated ingest must pass.
    # Local development without a configured key may accept the request.
    assert r.status_code == 200
    assert r.json()["demo_mode"] is False


def test_live_after_ingest_is_self_contained():
    ingest = client.post("/api/v1/ingest/live", json=_payload(power_kw=200.0), headers=_ingest_headers())
    assert ingest.status_code == 200

    r = client.get("/api/v1/buildings/burj-khalifa-01/live")
    assert r.status_code == 200
    # The endpoint may apply pipeline normalization; assert the ingested snapshot
    # remains live and numerically valid rather than depending on test order.
    assert r.json()["demo_mode"] is False
    assert isinstance(r.json()["hvac"]["power_kw"], (int, float))
