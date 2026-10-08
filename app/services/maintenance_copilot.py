"""Evidence-backed maintenance draft helper.

This intentionally does not call an LLM, create work orders, issue equipment
commands, or fabricate root causes. An authorized user must review every draft.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FaultEvidence(BaseModel):
    fault_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    observed_at: datetime
    measured_points: list[str] = Field(default_factory=list)
    description: str = ""


class MaintenanceDraft(BaseModel):
    fault_id: str
    asset_id: str
    title: str
    evidence_refs: list[str]
    review_status: str = "PENDING_HUMAN_REVIEW"
    diagnostic_steps: list[str]
    confidence: Optional[float] = None


def prepare_maintenance_draft(evidence: FaultEvidence) -> MaintenanceDraft:
    if evidence.observed_at.tzinfo is None:
        raise ValueError("Evidence timestamp must be timezone-aware")
    if not evidence.measured_points:
        raise ValueError("Cannot draft a diagnosis without measured evidence")
    return MaintenanceDraft(
        fault_id=evidence.fault_id,
        asset_id=evidence.asset_id,
        title=f"Review fault {evidence.rule_id} on {evidence.asset_id}",
        evidence_refs=list(dict.fromkeys(evidence.measured_points)),
        diagnostic_steps=[
            "Verify the recorded telemetry timestamps and sensor quality",
            "Inspect relevant equipment using approved site safety procedures",
            "Document findings and obtain authorized approval before any intervention",
        ],
    )
