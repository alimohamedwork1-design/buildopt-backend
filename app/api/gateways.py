"""BuildOpt Edge gateway registry, heartbeat, and fleet status."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.deps.auth import get_optional_user
from app.models.user_context import UserContext
from app.services.edge_heartbeat_store import edge_heartbeat_store
from app.services.ingest_auth import authorize_gateway, verify_ingest_key
from app.utils.arabic_utils import bilingual_error, bilingual_success
from fastapi import Depends

router = APIRouter(prefix="/gateways", tags=["gateways"])

CLOCK_DRIFT_DEGRADED_SECONDS = 120


class GatewayHeartbeat(BaseModel):
    gateway_id: str
    building_id: str
    tenant_id: str
    connector_id: str = "metasys"
    protocol: str = "edge"
    version: str = "1.0.0"
    connector_status: str = "ONLINE"
    telemetry_rate: int = 0
    queue_depth: int = 0
    oldest_queued_event_seconds: int | None = None
    events_uploaded_total: int = 0
    events_queued_total: int = 0
    events_replayed_total: int = 0
    upload_failures_total: int = 0
    last_successful_upload_at: datetime | None = None
    telemetry_rate_per_minute: float = 0.0
    edge_clock_at: datetime | None = None
    connector_error: str | None = None


@router.post("/heartbeat")
async def gateway_heartbeat(
    body: GatewayHeartbeat,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    verify_ingest_key(x_api_key)
    authorize_gateway(
        gateway_id=body.gateway_id,
        tenant_id=body.tenant_id,
        building_id=body.building_id,
        connector_id=body.connector_id,
    )

    cloud_now = datetime.now(timezone.utc)
    clock_drift_seconds = None
    gateway_state = body.connector_status
    if body.edge_clock_at:
        edge_ts = body.edge_clock_at
        if edge_ts.tzinfo is None:
            edge_ts = edge_ts.replace(tzinfo=timezone.utc)
        clock_drift_seconds = int(abs((cloud_now - edge_ts).total_seconds()))
        if clock_drift_seconds > CLOCK_DRIFT_DEGRADED_SECONDS and gateway_state == "ONLINE":
            gateway_state = "DEGRADED"

    edge_heartbeat_store.record_gateway(
        gateway_id=body.gateway_id,
        building_id=body.building_id,
        tenant_id=body.tenant_id,
        protocol=body.protocol,
        connector_id=body.connector_id,
        version=body.version,
        connector_status=gateway_state,
        telemetry_rate=body.telemetry_rate,
        queue_depth=body.queue_depth,
        oldest_queued_event_seconds=body.oldest_queued_event_seconds,
        events_uploaded_total=body.events_uploaded_total,
        events_queued_total=body.events_queued_total,
        events_replayed_total=body.events_replayed_total,
        upload_failures_total=body.upload_failures_total,
        last_successful_upload_at=body.last_successful_upload_at,
        telemetry_rate_per_minute=body.telemetry_rate_per_minute,
        clock_drift_seconds=clock_drift_seconds,
        edge_clock_at=body.edge_clock_at,
        connector_error=body.connector_error,
    )
    return {
        "status": "ok",
        "gateway_id": body.gateway_id,
        "gateway_state": gateway_state,
        "clock_drift_seconds": clock_drift_seconds,
        "message": bilingual_success("Gateway heartbeat recorded", "تم تسجيل نبضة البوابة"),
    }


@router.get("")
async def list_gateways(
    user: UserContext = Depends(get_optional_user),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    settings = get_settings()
    is_production = settings.app_env.lower() in ("production", "prod")
    has_key = bool(settings.ingest_api_key)
    if is_production and has_key:
        if x_api_key != settings.ingest_api_key and not user.authenticated:
            raise HTTPException(status_code=401, detail=bilingual_error("Authentication required", "المصادقة مطلوبة"))

    gateways = edge_heartbeat_store.list_gateways()
    if user.authenticated and user.building_ids:
        allowed = set(user.building_ids)
        gateways = [g for g in gateways if g.get("building_id") in allowed]
    return {"gateways": gateways}
