"""BuildOpt Edge gateway registry and heartbeat."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.edge_heartbeat_store import edge_heartbeat_store
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/gateways", tags=["gateways"])


class GatewayHeartbeat(BaseModel):
    gateway_id: str
    building_id: str
    tenant_id: str | None = None
    protocol: str = "edge"
    version: str = "1.0.0"
    connector_status: str = "ONLINE"
    telemetry_rate: int = 0
    queue_depth: int = 0
    last_read_at: datetime | None = None
    connector_error: str | None = None


@router.post("/heartbeat")
async def gateway_heartbeat(
    body: GatewayHeartbeat,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    from app.config import get_settings

    settings = get_settings()
    is_production = settings.app_env.lower() in ("production", "prod")
    if is_production and settings.ingest_api_key and x_api_key != settings.ingest_api_key:
        raise HTTPException(status_code=401, detail=bilingual_error("Invalid API key", "مفتاح API غير صالح"))

    edge_heartbeat_store.record_gateway(
        gateway_id=body.gateway_id,
        building_id=body.building_id,
        tenant_id=body.tenant_id,
        protocol=body.protocol,
        version=body.version,
        connector_status=body.connector_status,
        telemetry_rate=body.telemetry_rate,
        queue_depth=body.queue_depth,
        last_read_at=body.last_read_at,
        connector_error=body.connector_error,
    )
    return {
        "status": "ok",
        "gateway_id": body.gateway_id,
        "message": bilingual_success("Gateway heartbeat recorded", "تم تسجيل نبضة البوابة"),
    }


@router.get("")
async def list_gateways() -> dict:
    return {"gateways": edge_heartbeat_store.list_gateways()}
