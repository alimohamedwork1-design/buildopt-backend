"""Production-mode API invariants.

These tests intentionally differ from the demo regression suite: production endpoints must
require identity where appropriate and must not fabricate connectivity/history/data.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_live_business_endpoints_require_auth(prod_settings):
    client = TestClient(app)
    protected = [
        "/api/v1/buildings",
        "/api/v1/buildings/burj-khalifa-01/live",
        "/api/v1/energy/consumption",
        "/api/v1/alerts",
        "/api/v1/modules/overview/data",
        "/api/v1/data-health/buildings/burj-khalifa-01",
        "/api/v1/savings/opportunities",
        "/api/v1/recommendations",
    ]
    for path in protected:
        response = client.get(path)
        assert response.status_code == 401, (path, response.status_code, response.text)


def test_live_assistant_requires_auth(prod_settings):
    client = TestClient(app)
    response = client.post(
        "/api/v1/assistant/query",
        json={"building_id": "burj-khalifa-01", "tool": "building_live", "question": "What is live?"},
    )
    assert response.status_code == 401


def test_live_health_does_not_claim_unconfigured_metasys_connected(prod_settings):
    client = TestClient(app)
    response = client.get("/api/v1/health/protocols")
    assert response.status_code == 200
    protocols = response.json()["protocols"]
    metasys = next(p for p in protocols if p["name"] == "Metasys REST")
    assert metasys["status"] in {"not_configured", "disconnected", "degraded", "error"}
    assert metasys["status"] != "connected"


def test_live_health_history_can_be_empty_instead_of_fabricated(prod_settings):
    client = TestClient(app)
    response = client.get("/api/v1/health/history?hours=24")
    assert response.status_code == 200
    payload = response.json()
    assert payload["interval_minutes"] == 5
    assert isinstance(payload["data"], list)


def test_live_diagnostics_do_not_fake_success(prod_settings):
    client = TestClient(app)
    response = client.post(
        "/api/v1/jci/network-diagnostic",
        json={
            "host": "https://demo.metasys.invalid",
            "username": "test",
            "password": "test",
            "version": "v4",
        },
    )
    assert response.status_code == 200
    assert response.json()["overall"] != "pass"


def test_live_model_status_uses_truthful_engine_names(prod_settings):
    client = TestClient(app)
    response = client.get("/api/v1/ml/model-status")
    assert response.status_code == 200
    data = response.json()
    assert data["lstm_predictor"] == "history_gradient_boosting_pilot"
    assert data["mpc_optimizer"] == "bounded_rule_advisor_shadow_only"
    assert "lstm_v1" not in data.values()
    assert "mpc_v1" not in data.values()
