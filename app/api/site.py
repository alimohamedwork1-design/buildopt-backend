from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import get_settings
from app.data.modules_registry import list_modules
from app.deps.auth import UserContext, get_optional_user
from app.deps.guards import assert_building_access, empty_no_building
from app.services.pilot_os_service import build_pilot_summary, model_registry
from app.utils.arabic_utils import bilingual_error

router = APIRouter(prefix="/site", tags=["site"])


def _resolve_pilot_building(user: UserContext, requested: str | None) -> str:
    if requested:
        assert_building_access(user, requested)
        return requested
    if user.is_live_account:
        if not user.authenticated:
            raise HTTPException(
                status_code=401,
                detail=bilingual_error("Authentication required", "المصادقة مطلوبة"),
            )
        if not user.building_ids:
            raise HTTPException(status_code=404, detail=empty_no_building())
        return user.building_ids[0]
    return "burj-khalifa-01"


@router.get("/metadata")
async def site_metadata() -> dict:
    settings = get_settings()
    return {
        "name": "BuildOpt AI",
        "version": "3.1.0-pilot",
        "tagline": "Evidence-backed building intelligence for existing BMS",
        "frontend_url": "https://build-opt.site",
        "api_url": "https://buildopt-backend-production.up.railway.app",
        "timezone": settings.timezone,
        "locale": "en-AE",
        "currency": "AED",
        "demo_mode": settings.demo_mode,
        "modules_count": len(list_modules()),
        "features": {
            "live_api": True,
            "session_tracking": True,
            "module_api": True,
            "pilot_os": True,
            "semantic_mapping": True,
            "data_health": True,
            "fdd_lifecycle": True,
            "recommendation_approval": True,
            "measurement_verification": True,
            "shadow_optimization": True,
            "automatic_writeback": False,
            "bms_protocols": ["Metasys REST", "BACnet/IP", "Modbus TCP", "MQTT"],
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/config")
async def site_config() -> dict:
    settings = get_settings()
    return {
        "api_base": "/api/v1",
        "poll_intervals_ms": {
            "live": 5000,
            "alerts": 15000,
            "health": 30000,
            "energy": 60000,
        },
        "demo_mode": settings.demo_mode,
        "session_events_enabled": True,
        "pilot_os_enabled": True,
        "writeback_mode": "shadow_only",
    }


@router.get("/pilot/summary")
async def pilot_summary(
    building_id: str | None = Query(default=None),
    user: UserContext = Depends(get_optional_user),
) -> dict:
    resolved = _resolve_pilot_building(user, building_id)
    return await build_pilot_summary(user, resolved)


@router.get("/pilot/readiness")
async def pilot_readiness(
    building_id: str | None = Query(default=None),
    user: UserContext = Depends(get_optional_user),
) -> dict:
    resolved = _resolve_pilot_building(user, building_id)
    summary = await build_pilot_summary(user, resolved)
    return {
        "building_id": resolved,
        "state": summary["state"],
        "readiness_score": summary["readiness_score"],
        "steps": summary["steps"],
        "blockers": summary["blockers"],
        "generated_at": summary["generated_at"],
    }


@router.get("/pilot/operations")
async def pilot_operations(
    building_id: str | None = Query(default=None),
    user: UserContext = Depends(get_optional_user),
) -> dict:
    resolved = _resolve_pilot_building(user, building_id)
    summary = await build_pilot_summary(user, resolved)
    return {
        "building_id": resolved,
        "state": summary["state"],
        "readiness_score": summary["readiness_score"],
        **summary["operations"],
        "safety": summary["safety"],
        "generated_at": summary["generated_at"],
    }


@router.get("/pilot/connections")
async def pilot_connections(
    building_id: str | None = Query(default=None),
    user: UserContext = Depends(get_optional_user),
) -> dict:
    resolved = _resolve_pilot_building(user, building_id)
    summary = await build_pilot_summary(user, resolved)
    return summary["connections"]


@router.get("/pilot/rule-packs")
async def pilot_rule_packs(
    building_id: str | None = Query(default=None),
    user: UserContext = Depends(get_optional_user),
) -> dict:
    resolved = _resolve_pilot_building(user, building_id)
    summary = await build_pilot_summary(user, resolved)
    return {
        "building_id": resolved,
        "rule_packs": summary["rule_packs"],
        "approved_semantic_keys": summary["points"]["approved_semantic_keys"],
    }


@router.get("/pilot/models")
async def pilot_models(
    user: UserContext = Depends(get_optional_user),
) -> dict:
    if user.is_live_account and not user.authenticated:
        raise HTTPException(
            status_code=401,
            detail=bilingual_error("Authentication required", "المصادقة مطلوبة"),
        )
    return {
        "models": model_registry(),
        "policy": {
            "automatic_writeback": False,
            "human_approval_required": True,
            "unvalidated_model_claims_allowed": False,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
