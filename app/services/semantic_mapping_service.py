"""Semantic Mapping V2 — registry-native suggestions, approval, review queue, audit."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.metasys_auto_mapper import LOGICAL_KEYS
from app.services.semantic_audit_store import get_semantic_audit_store
from app.services.semantic_mapper import AUTO_MAP_THRESHOLD, REVIEW_THRESHOLD, suggest_semantic_mappings

STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
STATUS_SUGGESTED = "SUGGESTED"
STATUS_UNMAPPED = "UNMAPPED"


def _semantic_snapshot(meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "semantic_key": meta.get("semantic_key"),
        "mapping_status": meta.get("mapping_status"),
        "equipment_id": meta.get("equipment_id"),
        "display_name": meta.get("display_name"),
        "unit_override": meta.get("unit_override"),
        "relationships": meta.get("relationships") or {},
        "confidence": meta.get("confidence"),
    }


def _resolve_display_status(meta: Dict[str, Any], suggestion: Optional[Dict[str, Any]]) -> str:
    ms = meta.get("mapping_status")
    if ms == STATUS_APPROVED:
        return STATUS_APPROVED
    if ms == STATUS_REJECTED:
        return STATUS_REJECTED
    if not suggestion or not suggestion.get("object_id"):
        return STATUS_UNMAPPED
    sug_status = suggestion.get("status", "")
    if sug_status == "AUTO_CANDIDATE":
        return STATUS_SUGGESTED
    if sug_status == "REVIEW_REQUIRED":
        return STATUS_REVIEW_REQUIRED
    return STATUS_UNMAPPED


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
        if meta.get("mapping_status") == STATUS_APPROVED and meta.get("semantic_key"):
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


def build_review_queue(
    points: List[Dict[str, Any]],
    *,
    merge: bool = True,
) -> List[Dict[str, Any]]:
    suggestions = suggest_registry_mappings(points, merge=merge)
    by_source: Dict[str, Dict[str, Any]] = {}
    for s in suggestions:
        oid = s.get("object_id")
        if oid:
            by_source[str(oid)] = s

    rows: List[Dict[str, Any]] = []
    for p in points:
        meta = dict(p.get("metadata") or {})
        sid = p["source_point_id"]
        sug = by_source.get(sid)
        current = p.get("current") or {}
        status = _resolve_display_status(meta, sug)
        has_data = current.get("last_value") is not None or current.get("last_value_text") is not None

        rows.append(
            {
                "point_id": p["id"],
                "source_point_id": sid,
                "source_name": p.get("source_name"),
                "source_path": p.get("source_path"),
                "source_type": p.get("source_type"),
                "raw_unit": p.get("raw_unit"),
                "gateway_id": p.get("gateway_id"),
                "connector_id": p.get("connector_id"),
                "last_seen_at": p.get("last_seen_at"),
                "data_available": has_data,
                "freshness_state": current.get("freshness_state"),
                "canonical_tag": meta.get("semantic_key") or (sug or {}).get("logical_key"),
                "canonical_name": LOGICAL_KEYS.get(
                    meta.get("semantic_key") or (sug or {}).get("logical_key", ""),
                    (sug or {}).get("canonical_name"),
                ),
                "equipment_id": meta.get("equipment_id") or meta.get("equipment"),
                "display_name": meta.get("display_name"),
                "confidence": meta.get("confidence") if meta.get("confidence") is not None else (sug or {}).get("confidence", 0),
                "reason": meta.get("reason") or (sug or {}).get("reason"),
                "status": status,
                "relationships": meta.get("relationships") or {},
                "vendor_name": (sug or {}).get("vendor_name"),
            }
        )
    return rows


def _apply_semantic_patch(
    store: Any,
    *,
    building_id: str,
    source_point_id: str,
    patch: Dict[str, Any],
    mapping_status: str,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    comment: Optional[str] = None,
    action: str = "EDITED",
    confidence: Optional[float] = None,
) -> Dict[str, Any]:
    points, _ = store.list_points(building_id=building_id, limit=500)
    target = next((p for p in points if p["source_point_id"] == source_point_id), None)
    if not target:
        raise ValueError("source_point_not_found")
    if target["building_id"] != building_id:
        raise ValueError("building_mismatch")

    if mapping_status == STATUS_APPROVED and confidence is not None and confidence < REVIEW_THRESHOLD:
        raise ValueError("confidence_too_low_for_approval")

    prev_meta = dict(target.get("metadata") or {})
    previous = _semantic_snapshot(prev_meta)
    meta = dict(prev_meta)
    meta["mapping_status"] = mapping_status
    if patch.get("semantic_key") is not None:
        meta["semantic_key"] = patch["semantic_key"]
    if patch.get("equipment_id") is not None:
        meta["equipment_id"] = patch["equipment_id"]
    if patch.get("display_name") is not None:
        meta["display_name"] = patch["display_name"]
    if patch.get("unit_override") is not None:
        meta["unit_override"] = patch["unit_override"]
    if patch.get("relationships") is not None:
        meta["relationships"] = patch["relationships"]
    if confidence is not None:
        meta["confidence"] = confidence
    if comment:
        meta["last_comment"] = comment

    ts = datetime.now(timezone.utc).isoformat()
    if mapping_status == STATUS_APPROVED:
        meta["approved_at"] = ts
        meta.pop("rejected_at", None)
    elif mapping_status == STATUS_REJECTED:
        meta["rejected_at"] = ts
        meta["rejection_reason"] = comment or meta.get("rejection_reason")
    elif action == "REVERTED":
        meta["reverted_at"] = ts

    updated = store.update_point_metadata(target["id"], meta)
    get_semantic_audit_store().record(
        point_id=target["id"],
        building_id=building_id,
        tenant_id=target.get("tenant_id"),
        gateway_id=target.get("gateway_id"),
        source_point_id=source_point_id,
        action=action,
        previous_state=previous,
        new_state=_semantic_snapshot(meta),
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        comment=comment,
        confidence=confidence or meta.get("confidence"),
    )
    return {
        "point_id": target["id"],
        "source_point_id": source_point_id,
        "semantic_key": meta.get("semantic_key"),
        "status": mapping_status,
        "metadata": updated.get("metadata") or meta,
    }


def approve_registry_mapping(
    store: Any,
    *,
    building_id: str,
    semantic_key: str,
    source_point_id: str,
    status: str = STATUS_APPROVED,
    confidence: Optional[float] = None,
    equipment_id: Optional[str] = None,
    display_name: Optional[str] = None,
    relationships: Optional[Dict[str, Any]] = None,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    patch: Dict[str, Any] = {"semantic_key": semantic_key}
    if equipment_id:
        patch["equipment_id"] = equipment_id
    if display_name:
        patch["display_name"] = display_name
    if relationships:
        patch["relationships"] = relationships
    return _apply_semantic_patch(
        store,
        building_id=building_id,
        source_point_id=source_point_id,
        patch=patch,
        mapping_status=status,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        comment=comment,
        action="APPROVED",
        confidence=confidence,
    )


def reject_registry_mapping(
    store: Any,
    *,
    building_id: str,
    source_point_id: str,
    reason: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
) -> Dict[str, Any]:
    return _apply_semantic_patch(
        store,
        building_id=building_id,
        source_point_id=source_point_id,
        patch={},
        mapping_status=STATUS_REJECTED,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        comment=reason,
        action="REJECTED",
    )


def edit_registry_mapping(
    store: Any,
    *,
    building_id: str,
    source_point_id: str,
    patch: Dict[str, Any],
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    points, _ = store.list_points(building_id=building_id, limit=500)
    target = next((p for p in points if p["source_point_id"] == source_point_id), None)
    if not target:
        raise ValueError("source_point_not_found")
    meta = target.get("metadata") or {}
    status = meta.get("mapping_status") or STATUS_REVIEW_REQUIRED
    return _apply_semantic_patch(
        store,
        building_id=building_id,
        source_point_id=source_point_id,
        patch=patch,
        mapping_status=status if status not in (STATUS_APPROVED, STATUS_REJECTED) else STATUS_REVIEW_REQUIRED,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        comment=comment,
        action="EDITED",
    )


def revert_registry_mapping(
    store: Any,
    *,
    building_id: str,
    source_point_id: str,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    points, _ = store.list_points(building_id=building_id, limit=500)
    target = next((p for p in points if p["source_point_id"] == source_point_id), None)
    if not target:
        raise ValueError("source_point_not_found")
    if target["building_id"] != building_id:
        raise ValueError("building_mismatch")
    prev_meta = dict(target.get("metadata") or {})
    previous = _semantic_snapshot(prev_meta)
    meta: Dict[str, Any] = {"mapping_status": STATUS_UNMAPPED, "reverted_at": datetime.now(timezone.utc).isoformat()}
    updated = store.update_point_metadata(target["id"], meta)
    get_semantic_audit_store().record(
        point_id=target["id"],
        building_id=building_id,
        tenant_id=target.get("tenant_id"),
        gateway_id=target.get("gateway_id"),
        source_point_id=source_point_id,
        action="REVERTED",
        previous_state=previous,
        new_state=_semantic_snapshot(meta),
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        comment=comment,
    )
    return {"point_id": target["id"], "source_point_id": source_point_id, "status": STATUS_UNMAPPED, "metadata": updated.get("metadata") or meta}


def build_collection_config(
    points: List[Dict[str, Any]],
    *,
    building_id: str,
    gateway_id: Optional[str] = None,
    config_version: Optional[str] = None,
    mapping_revision: Optional[int] = None,
    status: str = "ACTIVE",
) -> Dict[str, Any]:
    approved: List[Dict[str, Any]] = []
    mapping: Dict[str, str] = {}
    for p in points:
        if gateway_id and p.get("gateway_id") != gateway_id:
            continue
        meta = p.get("metadata") or {}
        if meta.get("mapping_status") != STATUS_APPROVED or not meta.get("semantic_key"):
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
                "raw_unit": meta.get("unit_override") or p.get("raw_unit"),
                "equipment_id": meta.get("equipment_id"),
                "display_name": meta.get("display_name"),
                "expected_interval_seconds": p.get("expected_interval_seconds", 30),
                "relationships": meta.get("relationships") or {},
            }
        )

    unmapped = sum(
        1 for p in points
        if (p.get("metadata") or {}).get("mapping_status") not in (STATUS_APPROVED, STATUS_REJECTED)
    )
    gw = gateway_id or (points[0].get("gateway_id") if points else None)
    return {
        "version": 2,
        "building_id": building_id,
        "gateway_id": gw,
        "config_version": config_version,
        "mapping_revision": mapping_revision,
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mapping": mapping,
        "points": approved,
        "point_count": len(points),
        "approved_count": len(approved),
        "unmapped_count": unmapped,
    }


def review_queue_summary(queue: List[Dict[str, Any]]) -> Dict[str, Any]:
    groups = {
        "high_confidence": 0,
        "review_required": 0,
        "unmapped": 0,
        "approved": 0,
        "rejected": 0,
    }
    for row in queue:
        st = row.get("status")
        if st == STATUS_APPROVED:
            groups["approved"] += 1
        elif st == STATUS_REJECTED:
            groups["rejected"] += 1
        elif st == STATUS_REVIEW_REQUIRED:
            groups["review_required"] += 1
        elif st == STATUS_SUGGESTED and (row.get("confidence") or 0) >= AUTO_MAP_THRESHOLD:
            groups["high_confidence"] += 1
        elif st == STATUS_UNMAPPED:
            groups["unmapped"] += 1
        else:
            groups["review_required"] += 1
    return groups
