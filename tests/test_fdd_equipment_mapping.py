"""Regression tests for equipment-specific FDD checkers.

These tests deliberately exercise sensor keys declared in each rule, including
valid zero readings, and never require a connected BMS.
"""

import pytest

from app.services.fdd_rule_framework import ALL_RULES, RULE_CHECKS


@pytest.mark.parametrize("rule_id,readings,expected", [
    ("CH-003", {"chws_temp": 11, "chws_setpoint": 7}, True),
    ("CH-003", {"chws_temp": 7, "chws_setpoint": 7}, False),
    ("PUMP-001", {"pump_command": 1, "pump_status": 0}, True),
    ("PUMP-001", {"pump_command": 0, "pump_status": 0}, False),
    ("PUMP-002", {"differential_pressure": 1.2, "dp_setpoint": 0}, True),
    ("CT-001", {"cw_supply_temp": 33, "cw_supply_setpoint": 29}, True),
    ("FCU-001", {"zone_temp": 27, "zone_setpoint": 22}, True),
    ("FCU-002", {"valve_command": 75, "valve_feedback": 0}, True),
    ("VAV-001", {"damper_command": 75, "damper_feedback": 0}, True),
])
def test_equipment_specific_mapping(rule_id, readings, expected):
    rule = next(rule for rule in ALL_RULES if rule.rule_id == rule_id)
    assert set(rule.required_inputs).issubset(readings)
    assert RULE_CHECKS[rule.check](readings, rule.threshold) is expected


def test_missing_required_measurement_does_not_trigger():
    for rule_id in ("CH-003", "PUMP-001", "PUMP-002", "CT-001", "FCU-001", "FCU-002", "VAV-001"):
        rule = next(rule for rule in ALL_RULES if rule.rule_id == rule_id)
        assert RULE_CHECKS[rule.check]({}, rule.threshold) is False


def test_zero_setpoint_is_not_discarded():
    assert RULE_CHECKS["supply_air_temp_deviation"]({"supply_air_temp": 4, "supply_air_setpoint": 0, "sat_sp": 4}, 2)
