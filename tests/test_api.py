import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "demo_mode" in data


def test_list_buildings(client):
    response = client.get("/api/v1/buildings")
    assert response.status_code == 200
    buildings = response.json()
    assert len(buildings) >= 1
    assert buildings[0]["id"] == "burj-khalifa-01"


def test_live_data(client):
    response = client.get("/api/v1/buildings/burj-khalifa-01/live")
    assert response.status_code == 200
    data = response.json()
    assert data["building_id"] == "burj-khalifa-01"
    assert 180 <= data["hvac"]["power_kw"] <= 220
    assert 3.2 <= data["hvac"]["cop"] <= 4.1


def test_energy_endpoints(client):
    assert client.get("/api/v1/energy/consumption").status_code == 200
    assert client.get("/api/v1/energy/forecast").status_code == 200
    assert client.get("/api/v1/energy/dewa-tariff").status_code == 200
    assert client.get("/api/v1/energy/savings").status_code == 200


def test_alerts(client):
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    alerts = response.json()
    assert 2 <= len(alerts) <= 5


def test_gcc_prayer_times(client):
    response = client.get("/api/v1/gcc/prayer-times")
    assert response.status_code == 200
    data = response.json()
    assert "times" in data
    assert "fajr" in data["times"]
