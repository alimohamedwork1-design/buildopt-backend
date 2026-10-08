"""Read-only chiller efficiency calculations from explicitly supplied measurements.

No simulated plant telemetry or automatic savings claims. Engineering review
required for all results and operating decisions.
"""
from __future__ import annotations

from math import isfinite
from pydantic import BaseModel, Field, model_validator

KW_PER_TON = 3.51685284


class ChillerEfficiencyInput(BaseModel):
    chiller_id: str = Field(min_length=1, max_length=128)
    electrical_power_kw: float = Field(gt=0)
    cooling_capacity_kw: float = Field(gt=0)
    source: str = Field(default="USER_SUPPLIED")

    @model_validator(mode="after")
    def check_measurements(self):
        if not isfinite(self.electrical_power_kw) or not isfinite(self.cooling_capacity_kw):
            raise ValueError("Measurements must be finite")
        if self.source != "USER_SUPPLIED":
            raise ValueError("Only explicitly user-supplied inputs are supported")
        return self


def calculate_chiller_efficiency(data: ChillerEfficiencyInput) -> dict:
    tons = data.cooling_capacity_kw / KW_PER_TON
    return {
        "chiller_id": data.chiller_id,
        "source": "USER_SUPPLIED",
        "verified": False,
        "cooling_capacity_rt": round(tons, 4),
        "kw_per_rt": round(data.electrical_power_kw / tons, 4),
        "cop": round(data.cooling_capacity_kw / data.electrical_power_kw, 4),
        "assessment": "Calculated from supplied values; verify sensor accuracy and operating conditions",
        "bms_mode": "READ_ONLY",
    }
