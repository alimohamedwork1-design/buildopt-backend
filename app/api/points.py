"""Raw point registry and current-state read APIs."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from app.services.ingest_auth import verify_ingest_key
from app.services.telemetry_store import get_telemetry_store
from app.utils.arabic_utils import bilingual_error
from app.deps.auth import get_optional_user
from app.models.user_context import UserContext
from fastapi import Depends

router = APIRouter(prefix="/points", tags=["points"])


def _serialize_point(point: dict) -> dict:
    current = point.get("current") or {}
    return {
        "id": point["id"],
        "tenant_id": point["tenant_id"],
        "building_id": point["building_id"],
        "gateway_id": point["gateway_id"],
        "connector_id": point["connector_id"],
        "source": point["source"],
        "source_point_id": point["source_point_id"],
        "source_name": point.get("source_name"),
        "source_path": point.get("source_path"),
        "source_type": point.get("source_type"),
        "raw_unit": point.get("raw_unit"),
        "metadata": point.get("metadata") or {},
        "discovered_at": point.get("discovered_at"),
        "last_seen_at": point.get("last_seen_at"),
        "enabled": bool(point.get("enabled", 1)),
        "expected_interval_seconds": point.get("expected_interval_seconds", 30),
        "current": {
            "last_value": current.get("last_value") if current.get("last_value") is not None else current.get("last_value_text"),
            "last_source_timestamp": current.get("last_source_timestamp"),
            "last_edge_received_at": current.get("last_edge_received_at"),
            "last_cloud_received_at": current.get("last_cloud_received_at"),
            "source_quality": current.get("source_quality"),
            "normalized_quality": current.get("normalized_quality"),
            "freshness_seconds": current.get("freshness_seconds"),
            "expected_interval_seconds": current.get("expected_interval_seconds"),
            "freshness_state": current.get("freshness_state"),
            "state": current.get("state"),
        }
        if current
        else None,
    }


@router.get("")
async def list_points(
    tenant_id: Optional[str] = Query(default=None),
    building_id: Optional[str] = Query(default=None),
    gateway_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    verify_ingest_key(x_api_key)
    store = get_telemetry_store()
    points, total = store.list_points(
        tenant_id=tenant_id,
        building_id=building_id,
        gateway_id=gateway_id,
        limit=limit,
        offset=offset,
    )
    return {
        "points": [_serialize_point(p) for p in points if p],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{point_id}")
async def get_point(
    point_id: str,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    verify_ingest_key(x_api_key)
    store = get_telemetry_store()
    point = store.get_point(point_id)
    if not point:
        raise HTTPException(status_code=404, detail=bilingual_error("Point not found", "النقطة غير موجودة"))
    return {"point": _serialize_point(point)}


@router.get("/{point_id}/current")
async def get_point_current(
    point_id: str,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    user: UserContext = Depends(get_optional_user),
) -> dict:
    if x_api_key:
        verify_ingest_key(x_api_key)
    elif user.is_live_account and not user.authenticated:
        raise HTTPException(status_code=401, detail=bilingual_error("Authentication required", "المصادقة مطلوبة"))
    store = get_telemetry_store()
    point = store.get_point(point_id)
    if not point:
        raise HTTPException(status_code=404, detail=bilingual_error("Point not found", "النقطة غير موجودة"))
    if user.authenticated and user.building_ids and point["building_id"] not in user.building_ids:
        raise HTTPException(status_code=403, detail=bilingual_error("Access denied", "الوصول مرفوض"))
    return {"point_id": point_id, "current": _serialize_point(point).get("current")}
