import pytest
from pydantic import ValidationError

from app.services.scenario_constraints import ReadOnlyScenario, ScenarioState

BASE = dict(building_id="B1", asset_id="CH1", scenario_name="Offline trial", parameter="chws_setpoint_c", proposed_value=7.0, unit="degC")


def test_scenario_is_blocked_without_validated_model():
    assert ReadOnlyScenario(**BASE).state == ScenarioState.BLOCKED


def test_validated_offline_scenario_can_be_queued_for_simulation():
    result = ReadOnlyScenario(**BASE, baseline_source="validated historical baseline", model_validated=True)
    assert result.state == ScenarioState.READY_FOR_OFFLINE_SIMULATION
    assert not hasattr(result, "write_to_bms")


@pytest.mark.parametrize("change", [{"proposed_value": 1.0}, {"unit": "F"}, {"parameter": "fan_start_command"}])
def test_unsafe_or_command_parameters_rejected(change):
    with pytest.raises(ValidationError):
        ReadOnlyScenario(**{**BASE, **change})
