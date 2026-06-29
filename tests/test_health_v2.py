import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_score(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "health_score" in data
    assert 0 <= data["health_score"] <= 100
    assert "health_label" in data
    assert "health_label_ar" in data
    assert "uptime_seconds" in data


def test_health_protocols_v2(client):
    response = client.get("/api/v1/health/protocols")
    assert response.status_code == 200
    data = response.json()
    assert "protocols" in data
    assert len(data["protocols"]) >= 5
    assert data["overall_health"] in ("healthy", "degraded")
    metasys = next(p for p in data["protocols"] if p["name"] == "Metasys REST")
    assert metasys["status"] == "connected"
    assert metasys.get("key") == "metasys"
    assert data.get("jci_metasys") == "connected"


def test_health_history(client):
    response = client.get("/api/v1/health/history?hours=24")
    assert response.status_code == 200
    data = response.json()
    assert data["interval_minutes"] == 5
    assert len(data["data"]) >= 100
    assert data["history"] == data["data"]
    point = data["data"][0]
    assert "timestamp" in point
    assert "response_ms" in point
    assert "status" in point


def test_health_logs(client):
    response = client.get("/api/v1/health/logs?limit=10")
    assert response.status_code == 200
    logs = response.json()["logs"]
    assert 1 <= len(logs) <= 10
    assert "timestamp" in logs[0]
    assert "level" in logs[0]
    assert "message" in logs[0]


def test_health_pipeline(client):
    response = client.get("/api/v1/health/pipeline")
    assert response.status_code == 200
    jobs = response.json()["jobs"]
    assert len(jobs) >= 5
    job = jobs[0]
    assert "name" in job
    assert "name_ar" in job
    assert "last_run_human" in job
    assert "next_run_human" in job


def test_jci_test_connection_live_probe(client, monkeypatch):
    async def fake_test(*_a, **_k):
        return {"status": "connected", "response_ms": 120, "server_version": "v4", "ssl_valid": True}

    from app.services import jci_metasys

    monkeypatch.setattr(jci_metasys.JCIMetasysClient, "test_connection", fake_test)

    response = client.post(
        "/api/v1/jci/test-connection",
        json={
            "host": "https://demo.metasys.com",
            "username": "test",
            "password": "test",
            "version": "v4",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "connected"


def test_jci_network_diagnostic_demo(client):
    response = client.post(
        "/api/v1/jci/network-diagnostic",
        json={
            "host": "https://demo.metasys.com",
            "username": "test",
            "password": "test",
            "version": "v4",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["overall"] == "pass"
    assert len(data["checks"]) >= 5


def test_jci_save_credentials_demo(client):
    response = client.post(
        "/api/v1/jci/save-credentials",
        json={
            "host": "https://metasys.building.com",
            "username": "buildopt_api",
            "password": "secret",
            "version": "v4",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "saved"
    assert "message_ar" in data
