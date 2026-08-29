"""Phase 4 — registry-backed data health and per-point drilldown."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps.auth import UserContext
from app.deps.guards import assert_building_access, empty_no_building, require_module_enabled
from app.services.data_health_engine import building_data_health, registry_building_data_health, registry_point_health
from app.services import live_data_service
from app.services.metasys_object_store import get_metasys_objects
from app.services.telemetry_store import TelemetryStoreUnavailableError, get_telemetry_store

router = APIRouter(prefix="/data-health", tags=["data-health"])


@router.get("/buildings/{building_id}")
async def get_building_data_health(
    building_id: str,
    user: UserContext = Depends(require_module_enabled("data-health")),
):
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    assert_building_access(user, building_id)

    try:
        store = get_telemetry_store()
        tenant_id = user.user_id if user.authenticated else None
        points = store.list_building_current(building_id, tenant_id=tenant_id)
        if points:
            health = registry_building_data_health(points)
            return {"building_id": building_id, "available": True, **health}
    except TelemetryStoreUnavailableError:
        pass

    live = await live_data_service.get_live_data(building_id, user=user)
    if live:
        mapped = get_metasys_objects(building_id) or {}
        values = {
            "supply_air_temp": live.hvac.supply_air_temp,
            "return_air_temp": live.hvac.return_air_temp,
            "hvac_power_kw": live.hvac.power_kw,
            "total_kw": live.energy.total_kw,
            "temp_c": live.environment.temp_c,
            "co2_ppm": live.environment.co2_ppm,
            "humidity_pct": live.environment.humidity_pct,
        }
        health = building_data_health(mapped, values, observed_at=live.timestamp)
        return {"building_id": building_id, "available": True, "source": "legacy", **health}

    return {
        "building_id": building_id,
        "available": False,
        "state": "NO_DATA",
        "building_summary": {"status": "OFFLINE", "availability_pct": 0, "point_count": 0},
        "points": [],
        "source": "none",
    }


@router.get("/points/{point_id}")
async def get_point_data_health(
    point_id: str,
    user: UserContext = Depends(require_module_enabled("data-health")),
):
    try:
        store = get_telemetry_store()
    except TelemetryStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    point = store.get_point(point_id)
    if not point:
        raise HTTPException(status_code=404, detail="Point not found")
    assert_building_access(user, point["building_id"])
    health = registry_point_health(point)
    return {"point_id": point_id, "building_id": point["building_id"], **health}


@router.get("/buildings/{building_id}/points")
async def list_building_point_health(
    building_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    user: UserContext = Depends(require_module_enabled("data-health")),
):
    assert_building_access(user, building_id)
    try:
        store = get_telemetry_store()
    except TelemetryStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    tenant_id = user.user_id if user.authenticated else None
    points = store.list_building_current(building_id, tenant_id=tenant_id)
    results = [registry_point_health(p) for p in points]
    if status:
        results = [r for r in results if r.get("status") == status.upper()]
    total = len(results)
    page = results[offset : offset + limit]
    return {
        "building_id": building_id,
        "points": page,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
