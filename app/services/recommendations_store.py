"""Recommendation lifecycle store — durable via telemetry registry."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.services.telemetry_store import get_telemetry_store

VALID_TRANSITIONS: Dict[str, frozenset] = {
    "DETECTED": frozenset({"INVESTIGATING", "RECOMMENDED", "REJECTED", "CLOSED"}),
    "INVESTIGATING": frozenset({"RECOMMENDED", "REJECTED", "CLOSED"}),
    "RECOMMENDED": frozenset({"APPROVED", "REJECTED", "INVESTIGATING"}),
    "APPROVED": frozenset({"SCHEDULED", "IMPLEMENTED", "REJECTED"}),
    "SCHEDULED": frozenset({"IMPLEMENTED", "REJECTED"}),
    "IMPLEMENTED": frozenset({"MONITORING", "CLOSED"}),
    "MONITORING": frozenset({"VERIFIED", "CLOSED", "REJECTED"}),
    "VERIFIED": frozenset({"CLOSED"}),
    "REJECTED": frozenset({"CLOSED", "INVESTIGATING"}),
    "CLOSED": frozenset(),
}


class RecommendationState(str, Enum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    RECOMMENDED = "RECOMMENDED"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    IMPLEMENTED = "IMPLEMENTED"
    MONITORING = "MONITORING"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class Recommendation(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    building_id: str
    equipment_id: Optional[str] = None
    fault_id: Optional[str] = None
    rec_type: str = "fdd_action"
    title: str
    description: str = ""
    state: RecommendationState = RecommendationState.DETECTED
    severity: str = "warning"
    owner: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    recommended_action: Optional[str] = None
    expected_impact: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    risk: Optional[str] = None
    comfort_impact: Optional[str] = None
    verification_plan: Optional[str] = None
    expected_saving_aed: Optional[float] = None
    verified_saving_aed: Optional[float] = None
    approved_by: Optional[str] = None
    implemented_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    work_order_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _store():
    return get_telemetry_store()


def _to_model(row: Dict[str, Any]) -> Recommendation:
    data = dict(row)
    data["state"] = RecommendationState(data.get("state", "DETECTED"))
    for key in ("created_at", "updated_at", "implemented_at", "verified_at"):
        if data.get(key) and isinstance(data[key], str):
            try:
                data[key] = datetime.fromisoformat(str(data[key]).replace("Z", "+00:00"))
            except ValueError:
                pass
    if not data.get("recommended_action"):
        data["recommended_action"] = data.get("description")
    return Recommendation.model_validate(data)


def _to_row(rec: Recommendation) -> Dict[str, Any]:
    d = rec.model_dump(mode="json")
    d["state"] = rec.state.value
    return d


def list_recommendations(building_id: Optional[str] = None, *, limit: int = 100) -> List[Recommendation]:
    rows = _store().list_recommendations(building_id, limit=limit)
    return [_to_model(r) for r in rows]


def get_recommendation(rec_id: str) -> Optional[Recommendation]:
    row = _store().get_recommendation(rec_id)
    return _to_model(row) if row else None


def upsert_recommendation(rec: Recommendation) -> Recommendation:
    rec.updated_at = datetime.now(timezone.utc)
    row = _store().upsert_recommendation(_to_row(rec))
    return _to_model(row)


def transition_recommendation(
    rec_id: str,
    new_state: RecommendationState,
    *,
    actor_user_id: Optional[str] = None,
    comment: Optional[str] = None,
    approved_by: Optional[str] = None,
) -> Recommendation:
    rec = get_recommendation(rec_id)
    if not rec:
        raise ValueError("recommendation_not_found")
    prev = rec.state.value
    allowed = VALID_TRANSITIONS.get(prev, frozenset())
    if new_state.value not in allowed:
        raise ValueError(f"invalid_transition:{prev}->{new_state.value}")
    rec.state = new_state
    now = datetime.now(timezone.utc)
    if new_state == RecommendationState.APPROVED and approved_by:
        rec.approved_by = approved_by
    if new_state == RecommendationState.IMPLEMENTED:
        rec.implemented_at = now
    if new_state == RecommendationState.VERIFIED:
        rec.verified_at = now
    saved = upsert_recommendation(rec)
    _store().insert_recommendation_audit(
        audit_id=f"ra_{secrets.token_hex(8)}",
        recommendation_id=rec_id,
        action=f"transition_{new_state.value}",
        previous_state=prev,
        new_state=new_state.value,
        actor_user_id=actor_user_id,
        comment=comment,
    )
    return saved
