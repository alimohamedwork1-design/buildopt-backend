"""Discover Metasys objects and map them to BuildOpt logical telemetry keys."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

LOGICAL_KEYS: Dict[str, str] = {
    "supply_air_temp": "AHU / CHW supply air temperature (°C)",
    "return_air_temp": "AHU / CHW return air temperature (°C)",
    "hvac_power_kw": "HVAC or chiller electrical power (kW)",
    "total_kw": "Whole-building or main meter power (kW)",
    "temp_c": "Zone / space indoor temperature (°C)",
    "co2_ppm": "Indoor CO₂ (ppm)",
    "humidity_pct": "Relative humidity (%)",
    "pm25": "PM2.5 particulate (µg/m³)",
}

# (logical_key, name patterns) — first match wins per key
_NAME_RULES: List[Tuple[str, List[str]]] = [
    ("supply_air_temp", [r"\bsat\b", r"supply.?air", r"sa[\s_-]?temp", r"chw[\s_-]?sup", r"discharge.?air"]),
    ("return_air_temp", [r"\brat\b", r"return.?air", r"ra[\s_-]?temp", r"chw[\s_-]?ret", r"entering.?air"]),
    ("hvac_power_kw", [r"hvac.*kw", r"chiller.*kw", r"chw.*kw", r"cooling.*kw", r"plant.*kw", r"ch[\s_-]?\d+.*kw"]),
    ("total_kw", [r"total.*kw", r"building.*kw", r"main.*meter", r"em.*kw", r"site.*kw", r"whole.*building"]),
    ("temp_c", [r"zone.*temp", r"space.*temp", r"room.*temp", r"indoor.*temp", r"avg.*temp", r"oat"]),
    ("co2_ppm", [r"\bco2\b", r"carbon.?dioxide"]),
    ("humidity_pct", [r"humidity", r"\brh\b", r"relative.?hum"]),
    ("pm25", [r"pm2\.?5", r"pm25", r"particulate"]),
]


def normalize_metasys_object(raw: Any) -> Optional[Dict[str, str]]:
    """Extract id + searchable name from Metasys list/tree nodes."""
    if not isinstance(raw, dict):
        return None
    obj_id = str(
        raw.get("id")
        or raw.get("objectId")
        or raw.get("itemReference")
        or raw.get("reference")
        or ""
    ).strip()
    if not obj_id:
        return None
    name = str(
        raw.get("name")
        or raw.get("itemName")
        or raw.get("displayName")
        or raw.get("shortName")
        or raw.get("description")
        or ""
    ).strip()
    obj_type = str(raw.get("type") or raw.get("objectType") or "").strip()
    label = f"{name} {obj_type}".strip() or obj_id
    return {"id": obj_id, "name": name or obj_id, "type": obj_type, "label": label}


def flatten_metasys_objects(payload: Any) -> List[Dict[str, str]]:
    """Accept array, {items:[]}, or nested {children:[]}."""
    out: List[Dict[str, str]] = []
    seen: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        norm = normalize_metasys_object(node)
        if norm and norm["id"] not in seen:
            seen.add(norm["id"])
            out.append(norm)
        for child_key in ("items", "children", "objects", "members", "nodes"):
            if child_key in node and node[child_key]:
                walk(node[child_key])

    walk(payload)
    return out


def _score_name(label: str, patterns: List[str]) -> int:
    text = label.lower()
    for i, pat in enumerate(patterns):
        if re.search(pat, text, re.IGNORECASE):
            return 100 - i
    return 0


def suggest_mappings(
    objects: List[Dict[str, str]],
    existing: Optional[Dict[str, str]] = None,
    *,
    merge: bool = True,
) -> Dict[str, str]:
    """Heuristic map: logical_key -> Metasys object id."""
    existing = dict(existing or {})
    result = dict(existing) if merge else {}
    used_ids = set(result.values())

    for key, patterns in _NAME_RULES:
        if merge and key in result and result[key]:
            used_ids.add(result[key])
            continue
        best_id = ""
        best_score = 0
        for obj in objects:
            oid = obj["id"]
            if oid in used_ids:
                continue
            score = _score_name(obj.get("label") or obj.get("name") or "", patterns)
            if score > best_score:
                best_score = score
                best_id = oid
        if best_id and best_score > 0:
            result[key] = best_id
            used_ids.add(best_id)

    return result
