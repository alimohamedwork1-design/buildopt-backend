"""Batch telemetry ingestion from BuildOpt Edge — Phase 3 provenance pipeline."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.database import get_influx_service
from app.services.edge_heartbeat_store import edge_heartbeat_store
from app.services.ingest_auth import authorize_gateway, verify_ingest_key
from app.services.telemetry_pipeline import get_telemetry_pipeline
from app.services.telemetry_store import TelemetryStoreUnavailableError
from app.utils.arabic_utils import bilingual_success

logger = logging.getLogger("buildopt.telemetry.api")

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


class TelemetryEvent(BaseModel):
    event_id: Optional[str] = None
    source_point_id: str
    point_id: Optional[str] = None
    source: str = "metasys"
    source_name: Optional[str] = None
    source_path: Optional[str] = None
    source_type: Optional[str] = None
    source_timestamp: Optional[datetime] = None
    edge_received_at: Optional[datetime] = None
    timestamp: Optional[datetime] = None  # legacy alias for source_timestamp
    value: float | str | int
    raw_unit: Optional[str] = None
    unit: Optional[str] = None
    quality: Optional[str] = None
    source_quality: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tenant_id: Optional[str] = None
    building_id: Optional[str] = None


class TelemetryBatchRequest(BaseModel):
    gateway_id: str
    building_id: str
    tenant_id: str
    connector_id: str = "metasys"
    readings: List[TelemetryEvent] = Field(default_factory=list)


@router.post("/batch")
async def ingest_telemetry_batch(
    body: TelemetryBatchRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    verify_ingest_key(x_api_key, gateway_id=body.gateway_id)
    authorize_gateway(
        gateway_id=body.gateway_id,
        tenant_id=body.tenant_id,
        building_id=body.building_id,
        connector_id=body.connector_id,
    )

    if not body.readings:
        return {
            "accepted": 0,
            "rejected": 0,
            "duplicates": 0,
            "stored": 0,
            "message": bilingual_success("Empty batch acknowledged", "تم تأكيد دفعة فارغة"),
        }

    raw_readings: List[Dict[str, Any]] = []
    for r in body.readings:
        row = r.model_dump()
        if row.get("source_timestamp") is None and row.get("timestamp"):
            row["source_timestamp"] = row["timestamp"]
        if row.get("raw_unit") is None and row.get("unit"):
            row["raw_unit"] = row["unit"]
        raw_readings.append(row)

    try:
        result = get_telemetry_pipeline().process_batch(
            gateway_id=body.gateway_id,
            tenant_id=body.tenant_id,
            building_id=body.building_id,
            connector_id=body.connector_id,
            readings=raw_readings,
        )
    except TelemetryStoreUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "en": str(exc),
                "ar": "سجل القياس الدائم غير مُعد في الإنتاج",
                "telemetry_store": "not_configured",
            },
        ) from exc

    influx = get_influx_service()
    influx_state = influx.infrastructure_state()
    stored = 0
    if result.get("influx_rows"):
        stored = influx.write_telemetry_rows(result["influx_rows"])
        if stored < len(result["influx_rows"]) and influx_state["persistence"]:
            logger.warning(
                "Influx partial write stored=%s expected=%s",
                stored,
                len(result["influx_rows"]),
            )

    edge_heartbeat_store.record_gateway(
        gateway_id=body.gateway_id,
        building_id=body.building_id,
        tenant_id=body.tenant_id,
        protocol=body.connector_id,
        connector_id=body.connector_id,
        telemetry_rate=result["accepted"],
        connector_status="ONLINE",
    )

    return {
        "accepted": result["accepted"],
        "rejected": result["rejected"],
        "duplicates": result["duplicates"],
        "stored": stored if influx_state["persistence"] else result["accepted"],
        "rejections": result.get("rejections", []),
        "gateway_id": body.gateway_id,
        "building_id": body.building_id,
        "cloud_received_at": result["cloud_received_at"],
        "influx": influx_state,
        "message": bilingual_success("Telemetry batch processed", "تمت معالجة دفعة القياس"),
    }
