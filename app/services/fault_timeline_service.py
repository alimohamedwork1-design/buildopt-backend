"""Read-only fault replay timeline utilities.

Caller must authorize organization/building access and supply observed events
from trusted historical storage. This module never generates fake events.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from pydantic import BaseModel, Field


class ReplayEvent(BaseModel):
    event_id: str
    observed_at: datetime
    kind: str
    source: str
    asset_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class ReplayWindow(BaseModel):
    start: datetime
    end: datetime
    events: list[ReplayEvent]
    count: int


def build_replay_window(
    events: Iterable[ReplayEvent], *, start: datetime, end: datetime,
    asset_id: str, limit: int = 5000,
) -> ReplayWindow:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Replay boundaries must have timezone information")
    if start > end:
        raise ValueError("Replay start cannot be after end")
    if limit < 1 or limit > 10000:
        raise ValueError("Replay limit must be 1..10000")
    selected = []
    for event in events:
        if event.observed_at.tzinfo is None:
            continue
        if event.asset_id == asset_id and start <= event.observed_at <= end:
            selected.append(event)
    selected.sort(key=lambda e: (e.observed_at.astimezone(timezone.utc), e.event_id))
    selected = selected[:limit]
    return ReplayWindow(start=start, end=end, events=selected, count=len(selected))
