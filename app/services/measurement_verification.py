"""Conservative energy M&V and portfolio benchmarking utilities.

These functions do not certify IPMVP compliance or verified savings.
Site-specific baseline adjustment, weather normalization and independent
verification must occur before a result can be labelled VERIFIED.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Optional


@dataclass(frozen=True)
class SavingsEstimate:
    baseline_kwh: float
    measured_kwh: float
    estimated_savings_kwh: float
    estimated_savings_pct: float
    verification_status: str
    reason: str


@dataclass(frozen=True)
class PortfolioIntensity:
    building_id: str
    energy_kwh: float
    conditioned_area_m2: float
    eui_kwh_m2: float
    comparison_status: str


def estimate_unverified_savings(
    *, baseline_kwh: Optional[float], measured_kwh: Optional[float],
    baseline_adjusted: bool = False, sufficient_coverage: bool = False,
) -> Optional[SavingsEstimate]:
    if baseline_kwh is None or measured_kwh is None:
        return None
    if not all(isfinite(v) and v >= 0 for v in (baseline_kwh, measured_kwh)):
        return None
    if baseline_kwh == 0:
        return None
    difference = baseline_kwh - measured_kwh
    status = "READY_FOR_INDEPENDENT_REVIEW" if baseline_adjusted and sufficient_coverage else "UNVERIFIED"
    return SavingsEstimate(
        baseline_kwh, measured_kwh, difference, 100 * difference / baseline_kwh,
        status, "Calculated difference only; not certified verified savings",
    )


def calculate_eui(*, building_id: str, energy_kwh: float, conditioned_area_m2: float) -> PortfolioIntensity:
    if not building_id or not isfinite(energy_kwh) or energy_kwh < 0:
        raise ValueError("Valid building and nonnegative measured energy required")
    if not isfinite(conditioned_area_m2) or conditioned_area_m2 <= 0:
        raise ValueError("Conditioned floor area must be positive")
    return PortfolioIntensity(
        building_id, energy_kwh, conditioned_area_m2,
        energy_kwh / conditioned_area_m2, "RAW_EUI_NOT_NORMALIZED",
    )
