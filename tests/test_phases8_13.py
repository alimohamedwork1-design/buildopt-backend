"""Phases 8-11 — extended FDD, baseline, recommendations, savings."""

from __future__ import annotations

import pytest

from app.services.baseline_engine import compute_historical_baseline, deviation_from_baseline
from app.services.fdd_rule_framework import ALL_RULES, FddRuleEngine, PUMP_RULES
from app.services.recommendation_engine import recommendation_from_fault
from app.services.savings_mv_engine import create_potential_savings, verify_savings, savings_from_baseline
from app.services.shadow_optimization_engine import shadow_optimize
from app.services.writeback_service import request_writeback, writeback_status, WRITEBACK_ENABLED
from app.models.user_context import UserContext


def test_phase8_rule_count():
    assert len(ALL_RULES) >= 20
    assert any(r.equipment_type == "PUMP" for r in PUMP_RULES)


def test_phase8_pump_rule_blocked_without_inputs():
    engine = FddRuleEngine()
    result = engine.evaluate_equipment(
        readings={},
        point_meta={},
        equipment_id="CHWP-01",
        equipment_type="PUMP",
        building_id="b1",
    )
    assert len(result["faults"]) == 0


def test_phase9_baseline_insufficient_data():
    b = compute_historical_baseline([])
    assert b["available"] is False
    assert b["state"] == "INSUFFICIENT_DATA"


def test_phase9_baseline_with_samples():
    series = [{"value": 100}, {"value": 110}, {"value": 105}, {"value": 108}]
    b = compute_historical_baseline(series)
    assert b["available"] is True
    dev = deviation_from_baseline(120, b)
    assert dev["deviation_pct"] > 0


def test_phase10_recommendation_from_fault():
    rec = recommendation_from_fault({
        "fault_id": "AHU-001:AHU-01",
        "rule_id": "AHU-001",
        "building_id": "b1",
        "severity": "warning",
        "confidence": 0.8,
        "observed_values": {"supply_air_temp": 28},
    })
    assert rec.fault_id == "AHU-001:AHU-01"
    assert rec.evidence["rule_id"] == "AHU-001"


def test_phase11_potential_not_verified():
    opp = create_potential_savings(
        opp_id="s1", building_id="b1", title="Test", baseline_kwh=1000, expected_kwh=900, data_coverage_pct=80,
    )
    assert opp.state.value == "POTENTIAL"
    assert opp.verified_saving_aed is None


def test_phase11_verify_requires_measurement_period():
    opp = create_potential_savings(
        opp_id="s2", building_id="b1", title="Test", baseline_kwh=1000, expected_kwh=900, data_coverage_pct=80,
    )
    monitored = verify_savings("s2", actual_kwh=850, measurement_days=5)
    assert monitored.state.value == "MONITORING"


def test_phase12_shadow_no_writeback():
    result = shadow_optimize(
        building_id="b1",
        current_setpoints={"supply_air_setpoint": 21},
        constraints={"min_supply_temp": 18},
        history_series=[{"value": 500}] * 10,
    )
    assert result["writeback_enabled"] is False


def test_phase13_writeback_disabled_by_default():
    assert WRITEBACK_ENABLED is False
    status = writeback_status()
    assert status["writeback_enabled"] is False


def test_phase13_writeback_rejected_when_disabled():
    user = UserContext(user_id="u1", email="test@test.com", authenticated=True, roles=["admin"])
    with pytest.raises(Exception):
        request_writeback(
            user, site_id="s1", point_id="SAT_SP", current_value=21, requested_value=22,
            min_value=18, max_value=26, max_step=1,
        )
