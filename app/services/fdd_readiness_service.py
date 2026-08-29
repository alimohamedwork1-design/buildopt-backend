"""FDD input readiness from approved semantic mappings — no diagnosis, coverage only."""

from __future__ import annotations

from typing import Any, Dict, List

# Configurable equipment rule templates (semantic keys required for FDD input)
EQUIPMENT_FDD_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "AHU": {
        "label": "Air Handling Unit",
        "required_keys": [
            "supply_air_temp",
            "return_air_temp",
            "temp_c",
            "humidity_pct",
        ],
        "optional_keys": ["co2_ppm", "hvac_power_kw"],
    },
    "CHILLER": {
        "label": "Chiller Plant",
        "required_keys": ["hvac_power_kw", "supply_air_temp", "return_air_temp"],
        "optional_keys": ["total_kw"],
    },
}


def _approved_keys_by_equipment(points: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    by_eq: Dict[str, List[str]] = {}
    for p in points:
        meta = p.get("metadata") or {}
        if meta.get("mapping_status") != "APPROVED" or not meta.get("semantic_key"):
            continue
        eq = str(meta.get("equipment_id") or meta.get("equipment") or "UNASSIGNED")
        by_eq.setdefault(eq, []).append(str(meta["semantic_key"]))
    return by_eq


def equipment_fdd_readiness(
    points: List[Dict[str, Any]],
    *,
    equipment_id: str,
    template_key: str = "AHU",
) -> Dict[str, Any]:
    template = EQUIPMENT_FDD_TEMPLATES.get(template_key, EQUIPMENT_FDD_TEMPLATES["AHU"])
    required = template["required_keys"]
    optional = template.get("optional_keys", [])
    mapped = _approved_keys_by_equipment(points).get(equipment_id, [])
    mapped_set = set(mapped)

    required_status = [
        {"key": k, "mapped": k in mapped_set, "label": k.replace("_", " ").upper()}
        for k in required
    ]
    optional_status = [
        {"key": k, "mapped": k in mapped_set, "label": k.replace("_", " ").upper()}
        for k in optional
    ]
    req_mapped = sum(1 for r in required_status if r["mapped"])
    coverage = round((req_mapped / len(required)) * 100, 1) if required else 0.0

    if coverage >= 100:
        status = "READY"
    elif coverage >= 50:
        status = "PARTIAL INPUT COVERAGE"
    else:
        status = "INSUFFICIENT INPUT COVERAGE"

    unmapped_candidates = [
        p for p in points
        if (p.get("metadata") or {}).get("mapping_status") not in ("APPROVED", "REJECTED")
        and p.get("source_name")
    ]

    return {
        "equipment_id": equipment_id,
        "template": template_key,
        "template_label": template["label"],
        "required": required_status,
        "optional": optional_status,
        "coverage_pct": coverage,
        "status": status,
        "mapped_keys": mapped,
        "missing_keys": [r["key"] for r in required_status if not r["mapped"]],
        "unmapped_candidate_count": len(unmapped_candidates),
    }


def building_equipment_readiness(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_eq = _approved_keys_by_equipment(points)
    equipment_ids = sorted(set(by_eq.keys()) | {"AHU-01", "CH-1"})
    results: List[Dict[str, Any]] = []
    for eq_id in equipment_ids:
        template = "CHILLER" if eq_id.upper().startswith("CH") else "AHU"
        row = equipment_fdd_readiness(points, equipment_id=eq_id, template_key=template)
        if row["mapped_keys"] or eq_id in ("AHU-01", "CH-1"):
            results.append(row)
    return results
