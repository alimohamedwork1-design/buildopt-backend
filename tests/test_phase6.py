"""Phase 6 — data quality engine, FDD input validation, historical quality."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.data_quality_engine import score_point, aggregate_scores
from app.services.fdd_fault_store import FddFaultStore, reset_fdd_fault_store
from app.services.fdd_input_validator import validate_fdd_inputs, READINESS_READY, READINESS_INSUFFICIENT
from app.services.fdd_rule_framework import FddRuleEngine
from app.services.historical_quality_service import analyze_history_series
from app.services.semantic_readings_service import build_semantic_readings
from app.services.telemetry_store import TelemetryStore, reset_telemetry_store


@pytest.fixture(autouse=True)
def fresh_store():
    store = TelemetryStore(":memory:")
    reset_telemetry_store(store)
    reset_fdd_fault_store(FddFaultStore(store))
    yield store
    reset_telemetry_store(None)
    reset_fdd_fault_store(None)


@pytest.fixture
def client():
    return TestClient(app)


def test_quality_score_explainable_components():
    result = score_point(value=22.5, quality="GOOD", freshness_seconds=30, expected_interval_seconds=300)
    assert "components" in result
    assert result["score"] > 0
    assert "availability" in result["components"]


def test_quality_no_fabrication_without_evidence():
    result = score_point(value=None)
    assert result["state"] == "NO_DATA"
    assert result["score"] == 0.0


def test_fdd_input_validation_blocked_when_missing():
    v = validate_fdd_inputs(required_keys=["supply_air_temp", "sat_sp"], readings={"supply_air_temp": 22.0})
    assert v["status"] != READINESS_READY
    assert "supply_air_temp" not in v["missing_keys"] or "sat_sp" in v["missing_keys"]


def test_fdd_input_validation_ready(fresh_store):
    v = validate_fdd_inputs(
        required_keys=["supply_air_temp", "sat_sp"],
        readings={"supply_air_temp": 22.0, "sat_sp": 21.0},
        point_meta={
            "supply_air_temp": {"quality": "GOOD", "freshness_seconds": 10},
            "sat_sp": {"quality": "GOOD", "freshness_seconds": 10},
        },
        history_available_hours=24,
    )
    assert v["status"] == READINESS_READY


def test_fdd_rule_no_fault_without_inputs():
    engine = FddRuleEngine()
    result = engine.evaluate_equipment(
        readings={},
        point_meta={},
        equipment_id="AHU-01",
        equipment_type="AHU",
        building_id="b1",
    )
    assert len(result["faults"]) == 0
    assert len(result["blocked"]) > 0


def test_fdd_rule_sat_deviation(fresh_store):
    engine = FddRuleEngine()
    result = engine.evaluate_equipment(
        readings={"supply_air_temp": 28.0, "supply_air_setpoint": 21.0},
        point_meta={
            "supply_air_temp": {"quality": "GOOD", "freshness_seconds": 10},
            "supply_air_setpoint": {"quality": "GOOD", "freshness_seconds": 10},
        },
        equipment_id="AHU-01",
        equipment_type="AHU",
        building_id="b1",
        history_hours=24,
    )
    assert any(f["rule_id"] == "AHU-001" for f in result["faults"])


def test_historical_quality_honest_when_no_quality_field():
    series = [{"timestamp": "2026-08-29T10:00:00Z", "value": 22.0}]
    result = analyze_history_series(series)
    assert result["quality_available"] is False
    assert result["sample_count"] == 1


def test_historical_quality_with_stored_quality():
    series = [
        {"timestamp": "2026-08-29T10:00:00Z", "value": 22.0, "quality": "GOOD"},
        {"timestamp": "2026-08-29T10:05:00Z", "value": 22.1, "quality": "GOOD"},
    ]
    result = analyze_history_series(series)
    assert result["quality_available"] is True
    assert result["score"] > 0


def test_fault_deduplication(fresh_store):
    store = FddFaultStore(fresh_store)
    fault = {
        "fault_id": "AHU-001:AHU-01",
        "rule_id": "AHU-001",
        "building_id": "b1",
        "equipment_id": "AHU-01",
        "equipment_type": "AHU",
        "severity": "warning",
        "confidence": 0.8,
        "evidence": {},
    }
    store.upsert_fault(fault)
    store.upsert_fault({**fault, "confidence": 0.85})
    rows = store.list_active("b1")
    assert len(rows) == 1
    assert rows[0]["confidence"] == 0.85


def test_semantic_readings_approved_only(fresh_store):
    fresh_store.register_gateway(gateway_id="gw-1", tenant_id="t1", building_id="b1", connector_id="metasys")
    p = fresh_store.upsert_raw_point({
        "tenant_id": "t1", "building_id": "b1", "gateway_id": "gw-1", "connector_id": "metasys",
        "source": "metasys", "source_point_id": "obj-sat", "source_name": "SAT",
    })
    fresh_store.update_point_metadata(p["id"], {"semantic_key": "supply_air_temp", "mapping_status": "APPROVED", "equipment_id": "AHU-01"})
    fresh_store.update_current_state(
        point_id=p["id"],
        value=22.5,
        source_timestamp=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        edge_received_at=None,
        cloud_received_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        source_quality="good",
        normalized_quality="GOOD",
        expected_interval_seconds=30,
    )
    readings, meta, approved = build_semantic_readings(fresh_store, building_id="b1")
    assert "supply_air_temp" in readings
    assert readings["supply_air_temp"] == 22.5
