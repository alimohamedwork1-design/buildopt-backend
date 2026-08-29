"""Historical quality analysis from Influx telemetry samples."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.data_quality_engine import aggregate_scores, score_point


def analyze_history_series(
    series: List[Dict[str, Any]],
    *,
    expected_interval_seconds: int = 300,
) -> Dict[str, Any]:
    """Score a historical window from Influx history API rows."""
    if not series:
        return {
            "state": "NO_DATA",
            "score": 0.0,
            "sample_count": 0,
            "components": {},
            "quality_available": False,
            "message": "NO_DATA — no historical samples",
        }

    has_quality_field = any(s.get("quality") is not None for s in series)
    point_scores: List[Dict[str, Any]] = []
    gap_count = 0
    prev_ts = None

    for row in series:
        ts = row.get("timestamp")
        if prev_ts and ts:
            gap_count += 1
        prev_ts = ts
        quality = row.get("quality") if has_quality_field else None
        point_scores.append(
            score_point(
                value=row.get("value"),
                quality=quality,
                sample_count=len(series),
                gap_count=gap_count,
                expected_interval_seconds=expected_interval_seconds,
            )
        )

    agg = aggregate_scores(point_scores, label="historical_window")
    return {
        **agg,
        "sample_count": len(series),
        "quality_available": has_quality_field,
        "message": None if series else "NO_DATA",
    }
