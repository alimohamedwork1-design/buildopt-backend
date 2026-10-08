"""Validation-only scenario model. No control outputs or BMS writes."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ScenarioState(str, Enum):
    DRAFT = "DRAFT"
    BLOCKED = "BLOCKED"
    READY_FOR_OFFLINE_SIMULATION = "READY_FOR_OFFLINE_SIMULATION"


class ReadOnlyScenario(BaseModel):
    building_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    scenario_name: str = Field(min_length=1)
    parameter: str
    proposed_value: float
    unit: str
    baseline_source: str | None = None
    model_validated: bool = False
    state: ScenarioState = ScenarioState.DRAFT

    @model_validator(mode="after")
    def validate_offline_scenario(self):
        # Conservative software bounds only; not a site engineering approval.
        allowed = {
            "chws_setpoint_c": (4.0, 14.0, "degC"),
            "supply_air_setpoint_c": (10.0, 22.0, "degC"),
        }
        if self.parameter not in allowed:
            raise ValueError("Unsupported offline scenario parameter")
        low, high, unit = allowed[self.parameter]
        if self.unit != unit or not low <= self.proposed_value <= high:
            raise ValueError("Scenario parameter outside software bounds or wrong unit")
        self.state = (
            ScenarioState.READY_FOR_OFFLINE_SIMULATION
            if self.baseline_source and self.model_validated
            else ScenarioState.BLOCKED
        )
        return self
