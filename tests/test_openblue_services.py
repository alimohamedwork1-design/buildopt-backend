"""OpenBlue hardening — data health, savings, semantic mapper, FDD rules."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.fault_detector import FaultDetector, FDD_RULES
from app.services.data_health_engine import aggregate_health, assess_point_health, building_data_health
from app.services.semantic_mapper import AUTO_MAP_THRESHOLD, REVIEW_THRESHOLD, suggest_semantic_mappings
from app.services.savings_engine import SavingsState, compute_opportunity, list_opportunities
from app.services.write_policy import ControlMaturity, DEFAULT_CONTROL_MATURITY, write_mode_metadata


@pytest.fixture
def client():
    return TestClient(app)


def test_fdd_rule_pack_has_ahu_chiller_rules():
    categories = {r["category"] for r in FDD_RULES}
    assert "AHU" in categories
    assert "Chiller" in categories
    assert len(FDD_RULES) >= 10


def test_fault_detector_not_evaluable_when_prerequisites_missing():
    detector = FaultDetector(demo_mode=False)
    results = detector.evaluate({"cop": 3.5})
    assert any(r.get("status") == "NOT_EVALUABLE" for r in results)


def test_fault_detector_simultaneous_heating_cooling():
    detector = FaultDetector(demo_mode=False)
    faults = detector.evaluate({"heating_valve_cmd": 80, "cooling_valve_cmd": 75})
    assert any(f.get("rule_id") == "FDD-002" for f in faults)


def test_data_health_aggregate_offline_when_empty():
    summary = aggregate_health([])
    assert summary["status"] == "UNKNOWN"
    assert summary["availability_pct"] == 0.0


def test_data_health_flatline_flag():
    result = assess_point_health(value=22.0, variance=0.0)
    assert "flatline" in result["flags"]


def test_building_data_health_with_mapped_points():
    health = building_data_health(
        {"supply_air_temp": "obj-1", "total_kw": "obj-2"},
        {"supply_air_temp": 18.5, "total_kw": 420.0},
    )
    assert health["building_summary"]["point_count"] == 2


def test_semantic_mapper_confidence_thresholds():
    assert AUTO_MAP_THRESHOLD == 0.95
    assert REVIEW_THRESHOLD == 0.75


def test_semantic_mapper_suggests_mappings():
    objects = [{"id": "ai-1", "label": "Supply Air Temp AHU-01"}]
    mappings = suggest_semantic_mappings(objects, merge=False)
    assert isinstance(mappings, list)


def test_savings_opportunity_potential_vs_verified():
    opp = compute_opportunity(
        opp_id="sav-1",
        building_id="b1",
        title="Reset SAT setpoint",
        baseline_kwh=1000,
        expected_kwh=850,
        data_coverage_pct=90,
    )
    assert opp.state == SavingsState.POTENTIAL
    assert opp.expected_saving_aed > 0
    assert opp.verified_saving_aed is None


def test_write_policy_control_maturity_default():
    meta = write_mode_metadata()
    assert meta["control_maturity"] == DEFAULT_CONTROL_MATURITY.value
    assert meta["control_maturity"] == ControlMaturity.L0_MONITOR.value


def test_data_health_api(client):
    response = client.get("/api/v1/data-health/buildings/burj-khalifa-01")
    assert response.status_code == 200
    data = response.json()
    assert data["building_id"] == "burj-khalifa-01"


def test_savings_opportunities_api(client):
    response = client.get("/api/v1/savings/opportunities")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_recommendations_api(client):
    response = client.get("/api/v1/recommendations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_assistant_query_api(client):
    response = client.post(
        "/api/v1/assistant/query",
        json={"building_id": "burj-khalifa-01", "tool": "building_live", "question": "What is live?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["tool"] == "building_live"


def test_request_id_header(client):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "test-correlation-id"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "test-correlation-id"
