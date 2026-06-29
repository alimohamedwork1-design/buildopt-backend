from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.models.schemas import LiveBuildingData
from app.services.edge_heartbeat_store import edge_heartbeat_store
from app.services.live_data_service import ingest_live_snapshot
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestHeartbeat(BaseModel):
    building_id: str
    protocol: str
    last_read_at: datetime | None = None
    data_points: int = 0


@router.post("/live", response_model=LiveBuildingData)
async def ingest_live(
    payload: LiveBuildingData,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> LiveBuildingData:
    settings = get_settings()
    is_production = settings.app_env.lower() in ("production", "prod")
    if is_production and not settings.ingest_api_key:
        raise HTTPException(
            status_code=503,
            detail=bilingual_error("Ingest API key not configured", "مفتاح الإدخال غير مُعد"),
        )
    if settings.ingest_api_key and x_api_key != settings.ingest_api_key:
        raise HTTPException(status_code=401, detail=bilingual_error("Invalid API key", "مفتاح API غير صالح"))

    data = payload.model_copy(update={"demo_mode": False})
    ingest_live_snapshot(data)
    return data


@router.post("/heartbeat")
async def ingest_heartbeat(
    body: IngestHeartbeat,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    settings = get_settings()
    is_production = settings.app_env.lower() in ("production", "prod")
    if is_production and settings.ingest_api_key and x_api_key != settings.ingest_api_key:
        raise HTTPException(status_code=401, detail=bilingual_error("Invalid API key", "مفتاح API غير صالح"))

    edge_heartbeat_store.record(
        body.building_id,
        body.protocol.lower(),
        body.last_read_at,
        body.data_points,
    )
    return {
        "status": "ok",
        "building_id": body.building_id,
        "protocol": body.protocol,
        "message": bilingual_success("Heartbeat recorded", "تم تسجيل نبضة الحافة"),
    }


@router.get("/status")
async def ingest_status() -> dict:
    settings = get_settings()
    is_production = settings.app_env.lower() in ("production", "prod")
    return {
        "ingest_enabled": bool(settings.ingest_api_key) or not settings.demo_mode,
        "ingest_key_required": is_production,
        "demo_mode": settings.demo_mode,
        "message": bilingual_success("Ingest endpoint ready", "نقطة الإدخال جاهزة"),
    }
