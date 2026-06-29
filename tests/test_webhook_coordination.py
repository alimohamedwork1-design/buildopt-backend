import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_alert_webhook_test_endpoint(client):
    response = client.post("/api/v1/health/alert-webhook/test")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("not_configured", "skipped", "ok", "failed")
    assert "demo_mode" in data or "message" in data
