"""Conservative read-only root cause evidence ranking.

Rules provide hypotheses, not confirmed diagnoses or AI-generated telemetry.
No vendor controls, commands or work-order writes are performed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FaultEvidence(BaseModel):
    point_id: str = Field(min_length=1, max_length=128)
    kind: Literal["chws_supply_temp_c", "chws_return_temp_c", "pump_run_feedback", "chiller_run_feedback", "ahu_supply_temp_c"]
    value: float
    observed_at: datetime

    @model_validator(mode="after")
    def timestamp_is_aware(self):
        if self.observed_at.tzinfo is None:
            raise ValueError("Evidence timestamp must be timezone-aware")
        return self


class Hypothesis(BaseModel):
    code: str
    title: str
    evidence_point_ids: list[str]
    review_required: bool = True
    confidence: Literal["RULE_MATCH_NOT_VALIDATED"] = "RULE_MATCH_NOT_VALIDATED"


def suggest_root_causes(evidence: list[FaultEvidence]) -> list[Hypothesis]:
    by_kind: dict[str, FaultEvidence] = {}
    for point in evidence:
        previous = by_kind.get(point.kind)
        if previous is None or point.observed_at > previous.observed_at:
            by_kind[point.kind] = point
    suggestions: list[Hypothesis] = []
    supply = by_kind.get("chws_supply_temp_c")
    ret = by_kind.get("chws_return_temp_c")
    pump = by_kind.get("pump_run_feedback")
    chiller = by_kind.get("chiller_run_feedback")
    if supply and ret and ret.value < supply.value:
        suggestions.append(Hypothesis(code="CHWS_DELTA_REVERSED", title="Review CHWS sensor mapping and water flow direction",
                                      evidence_point_ids=[supply.point_id, ret.point_id]))
    if pump and chiller and pump.value == 0 and chiller.value > 0:
        suggestions.append(Hypothesis(code="PUMP_FEEDBACK_MISMATCH", title="Review pump feedback, interlocks and point mapping",
                                      evidence_point_ids=[pump.point_id, chiller.point_id]))
    return suggestions
