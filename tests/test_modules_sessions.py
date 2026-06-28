import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_site_metadata():
    r = client.get("/api/v1/site/metadata")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "BuildOpt AI"
    assert data["modules_count"] > 100


def test_list_modules():
    r = client.get("/api/v1/modules")
    assert r.status_code == 200
    assert len(r.json()) > 50


def test_module_data_overview():
    r = client.get("/api/v1/modules/overview/data")
    assert r.status_code == 200
    data = r.json()
    assert "metric_cards" in data
    assert "live" in data or data.get("category") == "overview"


def test_module_data_fdd():
    r = client.get("/api/v1/modules/fdd/data")
    assert r.status_code == 200
    data = r.json()
    assert data["category"] == "fault_prediction"
    assert "fdd" in data


def test_session_login_event():
    r = client.post(
        "/api/v1/sessions/events",
        json={
            "event_type": "login",
            "email": "test@buildopt.ai",
            "role": "facility_manager",
            "metadata": {"test": True},
        },
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_session_stats():
    client.post("/api/v1/sessions/events", json={"event_type": "login", "email": "a@test.com"})
    r = client.get("/api/v1/sessions/stats")
    assert r.status_code == 200
    assert r.json()["total_logins"] >= 1
