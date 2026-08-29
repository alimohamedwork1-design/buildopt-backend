"""Telemetry provenance metadata — every live payload should be traceable."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

DataModeLiteral = Literal["DEMO", "LIVE"]
QualityLiteral = Literal["GOOD", "DEGRADED", "STALE", "OFFLINE", "INVALID", "UNKNOWN"]


class ProvenanceMetadata(BaseModel):
    source: Optional[str] = None
    mode: DataModeLiteral = "LIVE"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    quality: QualityLiteral = "UNKNOWN"
    freshness_seconds: Optional[int] = None
    connector: Optional[str] = None
    building_id: Optional[str] = None


def build_provenance(
    *,
    source: Optional[str],
    mode: DataModeLiteral,
    building_id: Optional[str] = None,
    connector: Optional[str] = None,
    quality: QualityLiteral = "GOOD",
    freshness_seconds: Optional[int] = None,
    observed_at: Optional[datetime] = None,
) -> dict:
    ts = observed_at or datetime.now(timezone.utc)
    return ProvenanceMetadata(
        source=source,
        mode=mode,
        timestamp=ts,
        quality=quality,
        freshness_seconds=freshness_seconds,
        connector=connector,
        building_id=building_id,
    ).model_dump(mode="json")
