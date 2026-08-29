"""Point discovery sync from BuildOpt Edge."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.services.ingest_auth import authorize_gateway, verify_ingest_key
from app.services.telemetry_store import get_telemetry_store
from app.utils.arabic_utils import bilingual_success

router = APIRouter(prefix="/discovery", tags=["discovery"])


class DiscoveryPoint(BaseModel):
    source: str = "metasys"
    source_point_id: str
    source_name: Optional[str] = None
    source_path: Optional[str] = None
    source_type: Optional[str] = None
    raw_unit: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    expected_interval_seconds: Optional[int] = 30


class DiscoveryBatchRequest(BaseModel):
    gateway_id: str
    building_id: str
    tenant_id: str
    connector_id: str = "metasys"
    points: List[DiscoveryPoint] = Field(default_factory=list)


@router.post("/points/batch")
async def discovery_points_batch(
    body: DiscoveryBatchRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    verify_ingest_key(x_api_key, gateway_id=body.gateway_id)
    authorize_gateway(
        gateway_id=body.gateway_id,
        tenant_id=body.tenant_id,
        building_id=body.building_id,
        connector_id=body.connector_id,
    )

    store = get_telemetry_store()
    registered = 0
    updated = 0
    rejected = 0
    rejections: List[Dict[str, str]] = []

    for idx, pt in enumerate(body.points):
        try:
            existing = store.find_point_by_source(
                tenant_id=body.tenant_id,
                connector_id=body.connector_id,
                source_point_id=pt.source_point_id,
            )
            store.upsert_raw_point(
                {
                    "tenant_id": body.tenant_id,
                    "building_id": body.building_id,
                    "gateway_id": body.gateway_id,
                    "connector_id": body.connector_id,
                    "source": pt.source,
                    "source_point_id": pt.source_point_id,
                    "source_name": pt.source_name,
                    "source_path": pt.source_path,
                    "source_type": pt.source_type,
                    "raw_unit": pt.raw_unit,
                    "metadata": pt.metadata,
                    "expected_interval_seconds": pt.expected_interval_seconds or 30,
                }
            )
            if existing:
                updated += 1
            else:
                registered += 1
        except Exception as exc:
            rejected += 1
            rejections.append({"index": str(idx), "reason": str(exc)})

    return {
        "registered": registered,
        "updated": updated,
        "rejected": rejected,
        "rejections": rejections,
        "total": len(body.points),
        "message": bilingual_success("Discovery batch processed", "تمت مزامنة اكتشاف النقاط"),
    }
