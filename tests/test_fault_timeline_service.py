from datetime import datetime, timedelta, timezone

import pytest

from app.services.fault_timeline_service import ReplayEvent, build_replay_window


def test_replay_filters_by_asset_time_and_sorts():
    now = datetime(2026, 10, 8, tzinfo=timezone.utc)
    events = [
        ReplayEvent(event_id="b", observed_at=now + timedelta(minutes=2), kind="alarm", source="metasys", asset_id="AHU1"),
        ReplayEvent(event_id="a", observed_at=now + timedelta(minutes=1), kind="telemetry", source="metasys", asset_id="AHU1"),
        ReplayEvent(event_id="other", observed_at=now, kind="alarm", source="metasys", asset_id="AHU2"),
    ]
    result = build_replay_window(events, start=now, end=now + timedelta(minutes=3), asset_id="AHU1")
    assert [e.event_id for e in result.events] == ["a", "b"]
    assert result.count == 2


def test_empty_history_does_not_generate_events():
    now = datetime(2026, 10, 8, tzinfo=timezone.utc)
    assert build_replay_window([], start=now, end=now, asset_id="AHU1").events == []


def test_invalid_time_window_rejected():
    now = datetime(2026, 10, 8, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        build_replay_window([], start=now + timedelta(seconds=1), end=now, asset_id="AHU1")
