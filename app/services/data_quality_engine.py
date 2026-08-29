"""Data Quality Engine — explainable point/equipment/building scoring."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class QualityState(str, Enum):
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"
    STALE = "STALE"
    NO_DATA = "NO_DATA"
    INVALID = "INVALID"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    FLATLINE = "FLATLINE"
    TIMESTAMP_ERROR = "TIMESTAMP_ERROR"


@dataclass
class QualityComponents:
    availability: float = 0.0
    freshness: float = 0.0
    completeness: float = 0.0
    validity: float = 0.0
    range_check: float = 0.0
    flatline: float = 0.0
    timestamp_integrity: float = 0.0
    sampling_consistency: float = 0.0
    unit_consistency: float = 1.0
    outlier_rate: float = 1.0

    def overall(self) -> float:
        weights = [
            self.availability,
            self.freshness,
            self.completeness,
            self.validity,
            self.range_check,
            self.flatline,
            self.timestamp_integrity,
            self.sampling_consistency,
            self.unit_consistency,
            self.outlier_rate,
        ]
        return round(sum(weights) / len(weights) * 100, 1)

    def to_dict(self) -> Dict[str, float]:
        return {
            "availability": self.availability,
            "freshness": self.freshness,
            "completeness": self.completeness,
            "validity": self.validity,
            "range_check": self.range_check,
            "flatline": self.flatline,
            "timestamp_integrity": self.timestamp_integrity,
            "sampling_consistency": self.sampling_consistency,
            "unit_consistency": self.unit_consistency,
            "outlier_rate": self.outlier_rate,
        }


def score_point(
    *,
    value: Any = None,
    quality: Optional[str] = None,
    freshness_seconds: Optional[int] = None,
    expected_interval_seconds: int = 300,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    variance: Optional[float] = None,
    source_timestamp: Optional[datetime] = None,
    unit: Optional[str] = None,
    expected_unit: Optional[str] = None,
    sample_count: int = 1,
    gap_count: int = 0,
) -> Dict[str, Any]:
    """Score a single point with explainable components."""
    components = QualityComponents()
    state = QualityState.NO_DATA
    reasons: List[str] = []

    if value is None:
        components.availability = 0.0
        reasons.append("no_value")
        return _result(state, components, reasons, force_zero=True)

    components.availability = 1.0
    components.completeness = 1.0 - min(1.0, gap_count / max(sample_count, 1))

    q = (quality or "").upper()
    if q in ("BAD", "INVALID", "COMMUNICATION_ERROR"):
        components.validity = 0.0
        state = QualityState.BAD
        reasons.append(f"quality_{q.lower()}")
    elif q in ("UNCERTAIN", "UNKNOWN"):
        components.validity = 0.5
        state = QualityState.UNCERTAIN
        reasons.append("quality_uncertain")
    else:
        components.validity = 1.0

    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        components.validity = 0.0
        state = QualityState.INVALID
        reasons.append("invalid_numeric")

    if freshness_seconds is not None:
        stale_threshold = expected_interval_seconds * 3
        if freshness_seconds > stale_threshold:
            components.freshness = 0.0
            state = QualityState.STALE
            reasons.append("stale")
        elif freshness_seconds > expected_interval_seconds:
            components.freshness = 0.5
            if state == QualityState.NO_DATA:
                state = QualityState.STALE
        else:
            components.freshness = 1.0
    elif source_timestamp is None:
        components.timestamp_integrity = 0.0
        state = QualityState.TIMESTAMP_ERROR
        reasons.append("missing_source_timestamp")
    else:
        components.timestamp_integrity = 1.0
        components.freshness = 1.0

    if min_value is not None or max_value is not None:
        try:
            numeric = float(value)
            if min_value is not None and numeric < min_value:
                components.range_check = 0.0
                state = QualityState.OUT_OF_RANGE
                reasons.append("below_min")
            elif max_value is not None and numeric > max_value:
                components.range_check = 0.0
                state = QualityState.OUT_OF_RANGE
                reasons.append("above_max")
            else:
                components.range_check = 1.0
        except (TypeError, ValueError):
            components.range_check = 0.0
    else:
        components.range_check = 1.0

    if variance is not None and variance == 0 and isinstance(value, (int, float)):
        components.flatline = 0.0
        if state in (QualityState.NO_DATA, QualityState.GOOD):
            state = QualityState.FLATLINE
        reasons.append("flatline")

    if unit and expected_unit and unit != expected_unit:
        components.unit_consistency = 0.0
        reasons.append("unit_mismatch")

    if state == QualityState.NO_DATA and components.overall() >= 70:
        state = QualityState.GOOD

    return _result(state, components, reasons)


def aggregate_scores(scores: List[Dict[str, Any]], *, label: str = "aggregate") -> Dict[str, Any]:
    if not scores:
        return {
            "label": label,
            "state": QualityState.NO_DATA.value,
            "score": 0.0,
            "components": QualityComponents().to_dict(),
            "point_count": 0,
        }
    avg_components = QualityComponents()
    keys = avg_components.to_dict().keys()
    for key in keys:
        setattr(avg_components, key, sum(s["components"].get(key, 0) for s in scores) / len(scores))
    overall = avg_components.overall()
    states = [s["state"] for s in scores]
    if overall < 50 or states.count(QualityState.NO_DATA.value) > len(states) * 0.5:
        agg_state = QualityState.BAD.value
    elif overall < 75:
        agg_state = QualityState.UNCERTAIN.value
    else:
        agg_state = QualityState.GOOD.value
    return {
        "label": label,
        "state": agg_state,
        "score": overall,
        "components": avg_components.to_dict(),
        "point_count": len(scores),
    }


def _result(state: QualityState, components: QualityComponents, reasons: List[str], *, force_zero: bool = False) -> Dict[str, Any]:
    score = 0.0 if force_zero else components.overall()
    return {
        "state": state.value,
        "score": score,
        "components": components.to_dict(),
        "reasons": reasons,
    }
