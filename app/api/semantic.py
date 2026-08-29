"""Phase 5 — semantic review queue, approval workflow, audit, config versioning."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps.auth import UserContext, get_optional_user
from app.deps.guards import assert_building_access, require_semantic_write
from app.services.collection_config_service import get_collection_config_service
from app.services.fdd_readiness_service import building_equipment_readiness, equipment_fdd_readiness
from app.services.semantic_audit_store import get_semantic_audit_store
from app.services.semantic_mapping_service import (
    approve_registry_mapping,
    build_collection_config,
    build_review_queue,
    edit_registry_mapping,
    reject_registry_mapping,
    revert_registry_mapping,
    review_queue_summary,
    suggest_registry_mappings,
)
from app.services.telemetry_store import get_telemetry_store
from app.utils.arabic_utils import bilingual_error, bilingual_success
from pydantic import BaseModel, Field

router = APIRouter(prefix="/semantic", tags=["semantic"])


class ApproveMappingRequest(BaseModel):
    semantic_key: str
    source_point_id: str
    confidence: Optional[float] = None
    equipment_id: Optional[str] = None
    display_name: Optional[str] = None
    relationships: dict = Field(default_factory=dict)
    comment: Optional[str] = None


class RejectMappingRequest(BaseModel):
    source_point_id: str
    reason: Optional[str] = None


class EditMappingRequest(BaseModel):
    source_point_id: str
    semantic_key: Optional[str] = None
    equipment_id: Optional[str] = None
    display_name: Optional[str] = None
    unit_override: Optional[str] = None
    relationships: Optional[dict] = None
    comment: Optional[str] = None


class RevertMappingRequest(BaseModel):
    source_point_id: str
    comment: Optional[str] = None


def _actor(user: UserContext) -> tuple[Optional[str], Optional[str]]:
    return user.user_id, user.email


@router.get("/buildings/{building_id}/review-queue")
async def get_review_queue(
    building_id: str,
    status: Optional[str] = Query(default=None),
    equipment: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    min_confidence: Optional[float] = Query(default=None),
    user: UserContext = Depends(get_optional_user),
) -> dict:
    assert_building_access(user, building_id)
    store = get_telemetry_store()
    points, total = store.list_points(building_id=building_id, limit=500)
    queue = build_review_queue(points)
    if status:
        queue = [r for r in queue if r.get("status") == status.upper()]
    if equipment:
        queue = [r for r in queue if (r.get("equipment_id") or "").lower() == equipment.lower()]
    if source:
        queue = [r for r in queue if (r.get("connector_id") or r.get("source_type") or "") == source]
    if min_confidence is not None:
        queue = [r for r in queue if (r.get("confidence") or 0) >= min_confidence]
    return {
        "building_id": building_id,
        "points": queue,
        "total": len(queue),
        "registry_total": total,
        "summary": review_queue_summary(build_review_queue(points)),
    }


@router.get("/buildings/{building_id}/suggestions")
async def get_semantic_suggestions(
    building_id: str,
    merge: bool = True,
    user: UserContext = Depends(get_optional_user),
) -> dict:
    assert_building_access(user, building_id)
    store = get_telemetry_store()
    points, _ = store.list_points(building_id=building_id, limit=500)
    suggestions = suggest_registry_mappings(points, merge=merge)
    return {
        "building_id": building_id,
        "suggestions": suggestions,
        "total": len(suggestions),
        "registry_points": len(points),
    }


@router.post("/buildings/{building_id}/approve")
async def approve_semantic_mapping(
    building_id: str,
    body: ApproveMappingRequest,
    user: UserContext = Depends(require_semantic_write),
) -> dict:
    assert_building_access(user, building_id)
    store = get_telemetry_store()
    uid, email = _actor(user)
    try:
        result = approve_registry_mapping(
            store,
            building_id=building_id,
            semantic_key=body.semantic_key,
            source_point_id=body.source_point_id,
            confidence=body.confidence,
            equipment_id=body.equipment_id,
            display_name=body.display_name,
            relationships=body.relationships,
            actor_user_id=uid,
            actor_email=email,
            comment=body.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not_found" in str(exc) else 400, detail=bilingual_error(str(exc), "فشل الاعتماد")) from exc
    return {"building_id": building_id, "mapping": result, "message": bilingual_success("Mapping approved", "تم اعتماد التعيين")}


@router.post("/buildings/{building_id}/reject")
async def reject_semantic_mapping(
    building_id: str,
    body: RejectMappingRequest,
    user: UserContext = Depends(require_semantic_write),
) -> dict:
    assert_building_access(user, building_id)
    store = get_telemetry_store()
    uid, email = _actor(user)
    try:
        result = reject_registry_mapping(
            store,
            building_id=building_id,
            source_point_id=body.source_point_id,
            reason=body.reason,
            actor_user_id=uid,
            actor_email=email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=bilingual_error(str(exc), "النقطة غير موجودة")) from exc
    return {"building_id": building_id, "mapping": result, "message": bilingual_success("Mapping rejected", "تم رفض التعيين")}


@router.post("/buildings/{building_id}/edit")
async def edit_semantic_mapping(
    building_id: str,
    body: EditMappingRequest,
    user: UserContext = Depends(require_semantic_write),
) -> dict:
    assert_building_access(user, building_id)
    store = get_telemetry_store()
    uid, email = _actor(user)
    patch = {k: v for k, v in body.model_dump().items() if k not in ("source_point_id", "comment") and v is not None}
    try:
        result = edit_registry_mapping(
            store,
            building_id=building_id,
            source_point_id=body.source_point_id,
            patch=patch,
            actor_user_id=uid,
            actor_email=email,
            comment=body.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=bilingual_error(str(exc), "النقطة غير موجودة")) from exc
    return {"building_id": building_id, "mapping": result, "message": bilingual_success("Mapping updated", "تم تحديث التعيين")}


@router.post("/buildings/{building_id}/revert")
async def revert_semantic_mapping(
    building_id: str,
    body: RevertMappingRequest,
    user: UserContext = Depends(require_semantic_write),
) -> dict:
    assert_building_access(user, building_id)
    store = get_telemetry_store()
    uid, email = _actor(user)
    try:
        result = revert_registry_mapping(
            store,
            building_id=building_id,
            source_point_id=body.source_point_id,
            actor_user_id=uid,
            actor_email=email,
            comment=body.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=bilingual_error(str(exc), "النقطة غير موجودة")) from exc
    return {"building_id": building_id, "mapping": result, "message": bilingual_success("Mapping reverted", "تم التراجع عن التعيين")}


@router.get("/buildings/{building_id}/audit")
async def list_semantic_audit(
    building_id: str,
    point_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    user: UserContext = Depends(get_optional_user),
) -> dict:
    assert_building_access(user, building_id)
    audit = get_semantic_audit_store()
    if point_id:
        events = audit.list_for_point(point_id, limit=limit)
    else:
        events = audit.list_for_building(building_id, limit=limit)
    return {"building_id": building_id, "events": events, "total": len(events)}


@router.get("/buildings/{building_id}/collection-config")
async def get_collection_config(
    building_id: str,
    gateway_id: Optional[str] = None,
    user: UserContext = Depends(get_optional_user),
) -> dict:
    assert_building_access(user, building_id)
    svc = get_collection_config_service()
    active = svc.get_active(building_id=building_id, gateway_id=gateway_id)
    if active:
        return active
    store = get_telemetry_store()
    points, _ = store.list_points(building_id=building_id, gateway_id=gateway_id, limit=500)
    return build_collection_config(points, building_id=building_id, gateway_id=gateway_id, status="DRAFT")


@router.post("/buildings/{building_id}/collection-config/publish")
async def publish_collection_config(
    building_id: str,
    gateway_id: Optional[str] = None,
    user: UserContext = Depends(require_semantic_write),
) -> dict:
    assert_building_access(user, building_id)
    svc = get_collection_config_service()
    published = svc.publish(building_id=building_id, gateway_id=gateway_id, tenant_id=user.user_id)
    return {"building_id": building_id, **published, "message": bilingual_success("Collection config published", "تم نشر إعدادات الجمع")}


@router.get("/buildings/{building_id}/collection-config/versions")
async def list_collection_config_versions(
    building_id: str,
    user: UserContext = Depends(get_optional_user),
) -> dict:
    assert_building_access(user, building_id)
    versions = get_collection_config_service().list_versions(building_id)
    return {"building_id": building_id, "versions": versions, "total": len(versions)}


@router.get("/buildings/{building_id}/equipment-readiness")
async def get_equipment_readiness(
    building_id: str,
    equipment_id: Optional[str] = None,
    user: UserContext = Depends(get_optional_user),
) -> dict:
    assert_building_access(user, building_id)
    store = get_telemetry_store()
    points, _ = store.list_points(building_id=building_id, limit=500)
    if equipment_id:
        template = "CHILLER" if equipment_id.upper().startswith("CH") else "AHU"
        return equipment_fdd_readiness(points, equipment_id=equipment_id, template_key=template)
    return {"building_id": building_id, "equipment": building_equipment_readiness(points)}
