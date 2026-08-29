from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps.auth import UserContext
from app.deps.guards import assert_building_access, empty_no_building, require_module_enabled
from app.services.data_health_engine import building_data_health
from app.services import live_data_service
from app.services.metasys_object_store import get_metasys_objects

router = APIRouter(prefix="/data-health", tags=["data-health"])


@router.get("/buildings/{building_id}")
async def get_building_data_health(
    building_id: str,
    user: UserContext = Depends(require_module_enabled("data-health")),
):
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    assert_building_access(user, building_id)

    mapped = get_metasys_objects(building_id) or {}
    live = await live_data_service.get_live_data(building_id, user=user)
    if not live:
        return {
            "building_id": building_id,
            "available": False,
            "state": "NO_DATA",
            "building_summary": {"status": "OFFLINE", "availability_pct": 0, "point_count": 0},
            "points": [],
        }

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
    return {"building_id": building_id, "available": True, **health}
