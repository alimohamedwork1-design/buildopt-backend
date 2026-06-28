from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import get_settings
from app.data.modules_registry import list_modules

router = APIRouter(prefix="/site", tags=["site"])


@router.get("/metadata")
async def site_metadata() -> dict:
    settings = get_settings()
    return {
        "name": "BuildOpt AI",
        "version": "3.0.1",
        "tagline": "Intelligent BMS Optimization for GCC",
        "frontend_url": "https://build-opt.site",
        "api_url": "https://buildopt-backend-production.up.railway.app",
        "building_default": "burj-khalifa-01",
        "building_name": "HQ Tower, Dubai Media City",
        "timezone": settings.timezone,
        "locale": "en-AE",
        "currency": "AED",
        "demo_mode": settings.demo_mode,
        "modules_count": len(list_modules()),
        "features": {
            "live_api": True,
            "session_tracking": True,
            "module_api": True,
            "gcc_prayer": True,
            "dewa_tariff": True,
            "fdd_rules": 50,
            "bms_protocols": ["Metasys", "BACnet", "Modbus", "MQTT"],
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/config")
async def site_config() -> dict:
    settings = get_settings()
    return {
        "api_base": "/api/v1",
        "default_building_id": "burj-khalifa-01",
        "poll_intervals_ms": {
            "live": 5000,
            "alerts": 15000,
            "health": 30000,
            "energy": 60000,
        },
        "demo_mode": settings.demo_mode,
        "session_events_enabled": True,
    }
