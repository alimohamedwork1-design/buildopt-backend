"""Semantic Mapping V2 — registry-backed suggestions, approval, edge collection config."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps.auth import UserContext, get_optional_user
from app.deps.guards import assert_building_access, require_write_access
from app.services.semantic_mapping_service import (
    approve_registry_mapping,
    build_collection_config,
    suggest_registry_mappings,
)
from app.services.telemetry_store import get_telemetry_store
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/semantic", tags=["semantic"])


class ApproveMappingRequest(BaseModel):
    semantic_key: str
    source_point_id: str
    status: str = "APPROVED"
    confidence: Optional[float] = None


class BulkApproveRequest(BaseModel):
    approvals: List[ApproveMappingRequest] = Field(default_factory=list)


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
    user: UserContext = Depends(require_write_access),
) -> dict:
    assert_building_access(user, building_id)
    store = get_telemetry_store()
    try:
        result = approve_registry_mapping(
            store,
            building_id=building_id,
            semantic_key=body.semantic_key,
            source_point_id=body.source_point_id,
            status=body.status,
            confidence=body.confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=bilingual_error(str(exc), "النقطة غير موجودة")) from exc
    return {
        "building_id": building_id,
        "mapping": result,
        "message": bilingual_success("Semantic mapping approved", "تم اعتماد التعيين الدلالي"),
    }


@router.post("/buildings/{building_id}/approve/bulk")
async def approve_semantic_mappings_bulk(
    building_id: str,
    body: BulkApproveRequest,
    user: UserContext = Depends(require_write_access),
) -> dict:
    assert_building_access(user, building_id)
    store = get_telemetry_store()
    approved: List[dict] = []
    errors: List[dict] = []
    for item in body.approvals:
        try:
            approved.append(
                approve_registry_mapping(
                    store,
                    building_id=building_id,
                    semantic_key=item.semantic_key,
                    source_point_id=item.source_point_id,
                    status=item.status,
                    confidence=item.confidence,
                )
            )
        except ValueError as exc:
            errors.append({"source_point_id": item.source_point_id, "error": str(exc)})
    return {
        "building_id": building_id,
        "approved": approved,
        "errors": errors,
        "message": bilingual_success("Bulk approval processed", "تمت معالجة الاعتماد الجماعي"),
    }


@router.get("/buildings/{building_id}/collection-config")
async def get_collection_config(
    building_id: str,
    gateway_id: Optional[str] = None,
    user: UserContext = Depends(get_optional_user),
) -> dict:
    assert_building_access(user, building_id)
    store = get_telemetry_store()
    points, _ = store.list_points(building_id=building_id, limit=500)
    config = build_collection_config(points, building_id=building_id, gateway_id=gateway_id)
    return config
