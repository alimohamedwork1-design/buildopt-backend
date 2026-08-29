"""Batch telemetry ingestion from BuildOpt Edge."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.edge_heartbeat_store import edge_heartbeat_store
from app.database import get_influx_service
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


class TelemetryReading(BaseModel):
    building_id: str
    point_id: str
    timestamp: datetime
    value: float | str | int
    unit: Optional[str] = None
    quality: str = "GOOD"
    source: str = "metasys"
    source_point_id: Optional[str] = None
    equipment_id: Optional[str] = None
    connector_id: Optional[str] = None
    gateway_id: Optional[str] = None
    tenant_id: Optional[str] = None


class TelemetryBatchRequest(BaseModel):
    gateway_id: str
    building_id: str
    tenant_id: Optional[str] = None
    readings: List[TelemetryReading] = Field(default_factory=list)


def _verify_ingest_key(x_api_key: str | None) -> None:
    settings = get_settings()
    is_production = settings.app_env.lower() in ("production", "prod")
    if is_production and not settings.ingest_api_key:
        raise HTTPException(
            status_code=503,
            detail=bilingual_error("Ingest API key not configured", "مفتاح الإدخال غير مُعد"),
        )
    if settings.ingest_api_key and x_api_key != settings.ingest_api_key:
        raise HTTPException(status_code=401, detail=bilingual_error("Invalid API key", "مفتاح API غير صالح"))


def _dedupe_readings(readings: List[TelemetryReading]) -> List[TelemetryReading]:
    seen: set[str] = set()
    out: List[TelemetryReading] = []
    for r in readings:
        key = f"{r.building_id}:{r.point_id}:{r.timestamp.isoformat()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


@router.post("/batch")
async def ingest_telemetry_batch(
    body: TelemetryBatchRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    """Validate, deduplicate, and store edge telemetry batch."""
    _verify_ingest_key(x_api_key)

    if not body.readings:
        return {
            "accepted": 0,
            "rejected": 0,
            "message": bilingual_success("Empty batch acknowledged", "تم تأكيد دفعة فارغة"),
        }

    unique = _dedupe_readings(body.readings)
    influx = get_influx_service()
    stored = 0
    for reading in unique:
        tags = {
            "building_id": reading.building_id,
            "point_id": reading.point_id,
            "source": reading.source,
            "gateway_id": body.gateway_id,
        }
        if isinstance(reading.value, (int, float)):
            if influx.write_point(
                measurement="telemetry_point",
                value=float(reading.value),
                tags=tags,
            ):
                stored += 1

    edge_heartbeat_store.record_gateway(
        gateway_id=body.gateway_id,
        building_id=body.building_id,
        tenant_id=body.tenant_id,
        protocol="edge",
        telemetry_rate=len(unique),
        queue_depth=0,
        connector_status="ONLINE",
    )

    return {
        "accepted": len(unique),
        "stored": stored,
        "rejected": len(body.readings) - len(unique),
        "gateway_id": body.gateway_id,
        "building_id": body.building_id,
        "message": bilingual_success("Telemetry batch ingested", "تم استلام دفعة القياس"),
    }
