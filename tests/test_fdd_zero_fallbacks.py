"""Regression tests: zero is a valid sensor measurement, not a missing value."""
from app.services.fdd_rule_framework import RULE_CHECKS


def test_zero_static_pressure_setpoint_is_preserved():
    assert RULE_CHECKS["static_pressure_tracking"]({"static_pressure": 2, "static_pressure_setpoint": 0, "static_pressure_sp": 2}, 0.3)


def test_zero_cooling_command_does_not_fall_back_to_alias():
    assert not RULE_CHECKS["simultaneous_heating_cooling"]({"heating_valve_cmd": 50, "cooling_valve_cmd": 0, "chwv": 50}, 1)


def test_zero_cooling_command_is_not_overridden_for_leakage():
    assert RULE_CHECKS["cooling_valve_leakage"]({"cooling_valve_cmd": 0, "chwv": 100, "supply_air_temp": 14, "return_air_temp": 24}, 95)


def test_zero_mixed_air_temp_is_not_replaced_by_alias():
    assert RULE_CHECKS["mat_inconsistency"]({"mixed_air_temp": 0, "mat": 20, "outdoor_air_temp": 10, "return_air_temp": 30, "oa_damper_feedback": 50}, 3)
