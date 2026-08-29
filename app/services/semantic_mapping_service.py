"""Semantic Mapping V2 — registry-native suggestions, approval, and edge collection config."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.metasys_auto_mapper import LOGICAL_KEYS
from app.services.semantic_mapper import suggest_semantic_mappings


def _registry_objects(points: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    return [
        {
            "id": p["source_point_id"],
            "label": p.get("source_name") or p.get("source_point_id") or "",
            "name": p.get("source_name") or "",
        }
        for p in points
        if p.get("enabled", True)
    ]


def _approved_from_registry(points: List[Dict[str, Any]]) -> Dict[str, str]:
    approved: Dict[str, str] = {}
    for p in points:
        meta = p.get("metadata") or {}
        if meta.get("mapping_status") == "APPROVED" and meta.get("semantic_key"):
            approved[str(meta["semantic_key"])] = p["source_point_id"]
    return approved


def suggest_registry_mappings(
    points: List[Dict[str, Any]],
    *,
    merge: bool = True,
) -> List[Dict[str, Any]]:
    existing = _approved_from_registry(points) if merge else {}
    objects = _registry_objects(points)
    suggestions = suggest_semantic_mappings(objects, existing, merge=merge)
    for row in suggestions:
        row["logical_key"] = row.get("logical_key") or row.get("canonical_name")
        row["canonical_name"] = LOGICAL_KEYS.get(row["logical_key"], row["logical_key"])
    return suggestions


def approve_registry_mapping(
    store: Any,
    *,
    building_id: str,
    semantic_key: str,
    source_point_id: str,
    status: str = "APPROVED",
    confidence: Optional[float] = None,
) -> Dict[str, Any]:
    points, _ = store.list_points(building_id=building_id, limit=500)
    target = next((p for p in points if p["source_point_id"] == source_point_id), None)
    if not target:
        raise ValueError("source_point_not_found")
    if target["building_id"] != building_id:
        raise ValueError("building_mismatch")

    if status == "APPROVED" and confidence is not None and confidence < 0.75:
        raise ValueError("confidence_too_low_for_approval")
    meta = dict(target.get("metadata") or {})
    meta.update(
        {
            "semantic_key": semantic_key,
            "mapping_status": status,
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    if confidence is not None:
        meta["confidence"] = confidence

    updated = store.update_point_metadata(target["id"], meta)
    return {
        "point_id": target["id"],
        "semantic_key": semantic_key,
        "source_point_id": source_point_id,
        "status": status,
        "metadata": updated.get("metadata") or meta,
    }


def build_collection_config(
    points: List[Dict[str, Any]],
    *,
    building_id: str,
    gateway_id: Optional[str] = None,
) -> Dict[str, Any]:
    approved: List[Dict[str, Any]] = []
    mapping: Dict[str, str] = {}
    for p in points:
        if gateway_id and p.get("gateway_id") != gateway_id:
            continue
        meta = p.get("metadata") or {}
        if meta.get("mapping_status") != "APPROVED" or not meta.get("semantic_key"):
            continue
        key = str(meta["semantic_key"])
        mapping[key] = p["source_point_id"]
        approved.append(
            {
                "logical_key": key,
                "canonical_name": LOGICAL_KEYS.get(key, key),
                "source_point_id": p["source_point_id"],
                "point_id": p["id"],
                "source_name": p.get("source_name"),
                "raw_unit": p.get("raw_unit"),
            }
        )

    gw = gateway_id or (points[0].get("gateway_id") if points else None)
    return {
        "version": 2,
        "building_id": building_id,
        "gateway_id": gw,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mapping": mapping,
        "points": approved,
    }
