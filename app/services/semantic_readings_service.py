"""Build FDD readings from approved semantic mappings + registry current state."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

STATUS_APPROVED = "APPROVED"


def build_semantic_readings(
    store: Any,
    *,
    building_id: str,
    equipment_id: Optional[str] = None,
    gateway_id: Optional[str] = None,
) -> Tuple[Dict[str, float], Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Returns (readings_by_semantic_key, point_meta_by_key, approved_points).
    Only APPROVED mappings with numeric current values are included.
    """
    points, _ = store.list_points(building_id=building_id, gateway_id=gateway_id, limit=500)
    readings: Dict[str, float] = {}
    meta_by_key: Dict[str, Dict[str, Any]] = {}
    approved: List[Dict[str, Any]] = []

    for p in points:
        md = p.get("metadata") or {}
        if md.get("mapping_status") != STATUS_APPROVED:
            continue
        sk = md.get("semantic_key")
        if not sk:
            continue
        eq = md.get("equipment_id")
        if equipment_id and eq and eq != equipment_id:
            continue

        state = store.get_current_state(p["id"]) if hasattr(store, "get_current_state") else None
        value = None
        quality = None
        freshness_seconds = None
        if state:
            value = state.get("last_value")
            quality = state.get("normalized_quality") or state.get("source_quality")
            freshness_seconds = state.get("freshness_seconds")
        if value is None:
            continue
        try:
            readings[str(sk)] = float(value)
        except (TypeError, ValueError):
            continue

        meta_by_key[str(sk)] = {
            "point_id": p["id"],
            "source_point_id": p.get("source_point_id"),
            "equipment_id": eq,
            "quality": quality,
            "freshness_seconds": freshness_seconds,
            "expected_interval_seconds": p.get("expected_interval_seconds") or 300,
            "unit": md.get("unit_override") or p.get("raw_unit"),
        }
        approved.append(p)

    return readings, meta_by_key, approved
