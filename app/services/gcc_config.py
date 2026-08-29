"""GCC reference configuration — tariffs, calendars, carbon factors (configurable, not hardcoded claims)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

GCC_TARIFFS: Dict[str, Dict[str, Any]] = {
    "UAE_DEWA": {
        "region": "UAE",
        "utility": "DEWA",
        "currency": "AED",
        "peak_rate": 0.38,
        "off_peak_rate": 0.28,
        "shoulder_rate": 0.32,
        "demand_charge_rate": 15.0,
        "district_cooling_supported": True,
    },
    "UAE_ADWEA": {
        "region": "UAE",
        "utility": "ADDC/TAQA",
        "currency": "AED",
        "peak_rate": 0.35,
        "off_peak_rate": 0.26,
        "shoulder_rate": 0.30,
        "demand_charge_rate": 14.0,
        "district_cooling_supported": True,
    },
    "KSA_SEC": {
        "region": "KSA",
        "utility": "SEC",
        "currency": "SAR",
        "peak_rate": 0.18,
        "off_peak_rate": 0.12,
        "shoulder_rate": 0.15,
        "demand_charge_rate": 8.0,
        "district_cooling_supported": False,
    },
}

GCC_CARBON_FACTORS: Dict[str, float] = {
    "UAE": 0.475,
    "KSA": 0.62,
    "QAT": 0.55,
    "BHR": 0.72,
    "OMN": 0.58,
}

GCC_CALENDARS: Dict[str, Dict[str, Any]] = {
    "GCC_STANDARD": {
        "weekend_days": [5, 6],
        "friday_index": 5,
        "ramadan_profile_supported": True,
    },
    "UAE": {
        "weekend_days": [5, 6],
        "friday_index": 5,
        "ramadan_profile_supported": True,
    },
    "KSA": {
        "weekend_days": [5, 6],
        "friday_index": 5,
        "ramadan_profile_supported": True,
    },
}


def get_tariff(tariff_id: str) -> Optional[Dict[str, Any]]:
    return GCC_TARIFFS.get(tariff_id)


def list_tariffs(region: Optional[str] = None) -> List[Dict[str, Any]]:
    items = list(GCC_TARIFFS.values())
    if region:
        items = [t for t in items if t.get("region") == region]
    return items


def get_carbon_factor(region: str) -> Optional[float]:
    return GCC_CARBON_FACTORS.get(region)


def get_calendar(calendar_id: str = "GCC_STANDARD") -> Dict[str, Any]:
    return GCC_CALENDARS.get(calendar_id, GCC_CALENDARS["GCC_STANDARD"])
