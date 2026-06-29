"""Industrial refrigeration logical keys and Metasys auto-mapping heuristics."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from app.services.metasys_auto_mapper import flatten_metasys_objects

REFRIGERATION_LOGICAL_KEYS: Dict[str, str] = {
    "suction_pressure_bar": "Suction line pressure (bar)",
    "discharge_pressure_bar": "Discharge / head pressure (bar)",
    "evap_temp_c": "Evaporator / cold room temperature (°C)",
    "superheat_k": "Compressor superheat (K)",
    "subcooling_k": "Liquid subcooling (K)",
    "compressor_kw": "Compressor rack electrical load (kW)",
    "defrost_active": "Defrost cycle active (0/1)",
    "refrig_cop": "Refrigeration system COP",
    "nh3_ppm": "Ammonia leak sensor (ppm)",
}

_REFRIG_NAME_RULES: List[Tuple[str, List[str]]] = [
    ("suction_pressure_bar", [r"suction.*press", r"suc.*bar", r"suction.*psi", r"low.?side.*press"]),
    ("discharge_pressure_bar", [r"discharge.*press", r"head.*press", r"high.?side.*press", r"cond.*press"]),
    ("evap_temp_c", [r"evap.*temp", r"box.*temp", r"cold.?room", r"freezer.*temp", r"case.*temp"]),
    ("superheat_k", [r"superheat", r"\bsh\b", r"sh[\s_-]?k"]),
    ("subcooling_k", [r"subcool", r"\bsc\b", r"sub.?cool"]),
    ("compressor_kw", [r"compressor.*kw", r"rack.*kw", r"ref.*kw", r"refrig.*kw"]),
    ("defrost_active", [r"defrost", r"dfr.*status", r"defrost.*active"]),
    ("refrig_cop", [r"refrig.*cop", r"system.*eff", r"rack.*cop", r"plant.*cop"]),
    ("nh3_ppm", [r"\bnh3\b", r"ammonia", r"leak.*ppm"]),
]


def _score_name(label: str, patterns: List[str]) -> int:
    text = label.lower()
    for i, pat in enumerate(patterns):
        if re.search(pat, text, re.IGNORECASE):
            return 100 - i
    return 0


def suggest_refrigeration_mappings(
    objects: List[Dict[str, str]],
    existing: Optional[Dict[str, str]] = None,
    *,
    merge: bool = True,
) -> Dict[str, str]:
    """Heuristic map: refrigeration logical_key -> Metasys object id."""
    existing = dict(existing or {})
    result = dict(existing) if merge else {}
    used_ids = set(result.values())

    for key, patterns in _REFRIG_NAME_RULES:
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


__all__ = [
    "REFRIGERATION_LOGICAL_KEYS",
    "flatten_metasys_objects",
    "suggest_refrigeration_mappings",
]
