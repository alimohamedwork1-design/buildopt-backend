"""Read-only engineering copilot: auditable draft with NO autonomous actions.

Operator-supplied point references are NOT checked against a customer's
historian by this endpoint. Evidence must be independently verified by a
controls engineer before findings may be represented as factual diagnoses.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.compatibility import require_assigned_building
from app.deps.auth import get_required_user
from app.models.user_context import UserContext
from app.services.maintenance_copilot import FaultEvidence, prepare_maintenance_draft

router = APIRouter(prefix="/engineering", tags=["engineering"])


class ReviewDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    building_id: str = Field(min_length=1, max_length=160)
    fault_id: str = Field(min_length=1, max_length=160)
    asset_id: str = Field(min_length=1, max_length=160)
    rule_id: str = Field(min_length=1, max_length=160)
    observed_at: datetime
    measured_points: list[str] = Field(min_length=1, max_length=32)
    question: str = Field(default="", max_length=1000)
    request_writeback: bool = False


@router.post("/review-draft")
async def engineering_review_draft(
    body: ReviewDraftRequest,
    user: UserContext = Depends(get_required_user),
) -> dict:
    require_assigned_building(user, body.building_id)
    if body.request_writeback:
        raise HTTPException(status_code=403, detail="Physical controls are never modified by this endpoint")
    if body.observed_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="Observation time must carry timezone")
    if body.observed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="Future observation timestamps are not accepted")
    unique_refs = list(dict.fromkeys(p.strip() for p in body.measured_points if p.strip()))
    if not unique_refs or len(unique_refs) > 32:
        raise HTTPException(status_code=422, detail="One to 32 valid source point IDs required")

    evidence = FaultEvidence(
        fault_id=body.fault_id,
        asset_id=body.asset_id,
        rule_id=body.rule_id,
        observed_at=body.observed_at,
        measured_points=unique_refs,
    )
    draft = prepare_maintenance_draft(evidence)
    return {
        "building_id": body.building_id,
        "fault_id": body.fault_id,
        "draft": draft.model_dump(mode="json"),
        "source_integrity": "UNVERIFIED_OPERATOR_SUPPLIED_REFERENCES",
        "readings_fetched": False,
        "fault_confirmed": False,
        "confidence": None,
        "verified_savings": None,
        "writeback_enabled": False,
        "automatic_work_order_created": False,
        "review_required": True,
        "limits": [
            "Point IDs and fault context came from operator input; no live telemetry was fetched.",
            "Verify point provenance, clock, units and quality against site data.",
            "Do not interpret this draft as a confirmed root cause, safety clearance, or setpoint command.",
        ],
        "recommended_next_step": "Verify the source evidence with the assigned engineer before action.",
    }
