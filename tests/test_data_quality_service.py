from datetime import datetime, timedelta, timezone

import pytest

from app.services.data_quality_service import DataQualityState, classify_telemetry

NOW = datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("value, timestamp", [(None, NOW), (0.0, None), (float("nan"), NOW), (float("inf"), NOW), (1.0, datetime(2026, 10, 8))])
def test_missing_invalid_or_untrusted_time_never_live(value, timestamp):
    result = classify_telemetry(value=value, observed_at=timestamp, source="metasys", now=NOW)
    assert result.state == DataQualityState.NO_DATA


def test_zero_is_valid_live_value():
    result = classify_telemetry(value=0.0, observed_at=NOW, source="metasys", now=NOW)
    assert result.state == DataQualityState.LIVE
    assert result.usable_for_verified_savings is False


def test_stale_data_is_not_live():
    result = classify_telemetry(value=12.0, observed_at=NOW - timedelta(minutes=6), source="metasys", now=NOW)
    assert result.state == DataQualityState.STALE


def test_demo_and_errors_never_live():
    assert classify_telemetry(value=1.0, observed_at=NOW, source="demo", now=NOW, demo=True).state == DataQualityState.DEMO
    assert classify_telemetry(value=1.0, observed_at=NOW, source="metasys", now=NOW, error=True).state == DataQualityState.ERROR


def test_future_timestamp_is_error():
    result = classify_telemetry(value=1.0, observed_at=NOW + timedelta(minutes=2), source="metasys", now=NOW)
    assert result.state == DataQualityState.ERROR


def test_bad_freshness_limit_rejected():
    with pytest.raises(ValueError):
        classify_telemetry(value=1.0, observed_at=NOW, source="metasys", now=NOW, max_age_seconds=0)
