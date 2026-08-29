"""Recommendation lifecycle store."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


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
    building_id: str
    title: str
    description: str
    state: RecommendationState = RecommendationState.DETECTED
    severity: str = "warning"
    owner: Optional[str] = None
    evidence: Dict = Field(default_factory=dict)
    expected_saving_aed: Optional[float] = None
    verified_saving_aed: Optional[float] = None
    fault_id: Optional[str] = None
    work_order_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


_STORE: Dict[str, Recommendation] = {}


def list_recommendations(building_id: Optional[str] = None) -> List[Recommendation]:
    items = list(_STORE.values())
    if building_id:
        items = [r for r in items if r.building_id == building_id]
    return sorted(items, key=lambda r: r.created_at, reverse=True)


def get_recommendation(rec_id: str) -> Optional[Recommendation]:
    return _STORE.get(rec_id)


def upsert_recommendation(rec: Recommendation) -> Recommendation:
    rec.updated_at = datetime.now(timezone.utc)
    _STORE[rec.id] = rec
    return rec
