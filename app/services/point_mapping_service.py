"""Deterministic, review-first mapping suggestions for BMS point names.

This module does not read/write equipment and does not automatically approve
mappings. Confidence is a heuristic score, not a calibrated ML probability.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PointMappingSuggestion:
    source_point: str
    equipment_id: Optional[str]
    semantic_key: Optional[str]
    confidence: float
    review_status: str
    reason: str


ALIASES: dict[str, tuple[str, ...]] = {
    "supply_air_temp": ("SAT", "SUPPLYAIRTEMP", "SUPPLYTEMP"),
    "return_air_temp": ("RAT", "RETURNAIRTEMP", "RETURNTEMP"),
    "outdoor_air_temp": ("OAT", "OUTDOORAIRTEMP", "OUTSIDETEMP"),
    "supply_air_setpoint": ("SATSP", "SUPPLYAIRSETPOINT"),
    "fan_status": ("FANSTATUS", "FANSTS", "FANRUN"),
    "fan_command": ("FANCMD", "FANCOMMAND"),
    "cooling_valve_cmd": ("CHWVCMD", "COOLINGVALVECMD"),
    "filter_dp": ("FILTERDP", "FILTERPRESSURE"),
    "co2_ppm": ("CO2", "CO2PPM"),
    "power_kw": ("POWERKW", "KW"),
}

def _tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^A-Z0-9]+", value.upper()) if token]


def suggest_point_mapping(point_name: str) -> PointMappingSuggestion:
    tokens = _tokens(point_name)
    if not tokens:
        return PointMappingSuggestion(point_name, None, None, 0.0, "PENDING_REVIEW", "Empty point name")
    equipment = next((token for token in tokens if re.fullmatch(r"(?:AHU|VAV|CH|CHLR|CHWP|CT|FCU)[0-9]{1,4}", token)), None)
    normalized = ["".join(tokens), *tokens]
    matches = [
        semantic for semantic, aliases in ALIASES.items()
        if any(candidate.endswith(alias) or candidate == alias for candidate in normalized for alias in aliases)
    ]
    if len(matches) != 1:
        return PointMappingSuggestion(point_name, equipment, None, 0.0, "PENDING_REVIEW", "Unknown or ambiguous semantic tag")
    semantic = matches[0]
    confidence = 0.85 if equipment else 0.55
    return PointMappingSuggestion(
        point_name, equipment, semantic, confidence, "PENDING_REVIEW",
        "Deterministic alias match; human approval and unit validation required",
    )
