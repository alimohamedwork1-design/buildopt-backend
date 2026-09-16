"""Evidence assistant tools — query real building data only for live accounts."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from app.models.user_context import UserContext
from app.services import live_data_service
from app.services.data_health_engine import building_data_health
from app.services.metasys_object_store import get_metasys_objects
from app.services.recommendations_store import list_recommendations
from app.services.savings_engine import list_opportunities

ToolFn = Union[
    Callable[..., Any],
    Callable[..., Awaitable[Any]],
]


async def tool_building_live(building_id: str, user: Optional[UserContext] = None) -> Dict[str, Any]:
    live = await live_data_service.get_live_data(building_id, user=user)
    if not live:
        return {"available": False, "reason": "NO_TELEMETRY", "building_id": building_id}
    return {"available": True, "data": live.model_dump(mode="json"), "source": live.source}


async def tool_data_health(building_id: str, user: Optional[UserContext] = None) -> Dict[str, Any]:
    mapped = get_metasys_objects(building_id) or {}
    live = await live_data_service.get_live_data(building_id, user=user)
    if not live:
        return {"available": False, "reason": "NO_TELEMETRY", "building_id": building_id}
    values = {
        "supply_air_temp": live.hvac.supply_air_temp,
        "return_air_temp": live.hvac.return_air_temp,
        "hvac_power_kw": live.hvac.power_kw,
        "total_kw": live.energy.total_kw,
        "temp_c": live.environment.temp_c,
        "co2_ppm": live.environment.co2_ppm,
    }
    return {
        "available": True,
        "building_id": building_id,
        "health": building_data_health(mapped, values, observed_at=live.timestamp),
        "source": live.source,
    }


def tool_recommendations(building_id: str, user: Optional[UserContext] = None) -> List[Dict[str, Any]]:
    return [r.model_dump(mode="json") for r in list_recommendations(building_id)]


def tool_savings_opportunities(building_id: str, user: Optional[UserContext] = None) -> List[Dict[str, Any]]:
    return [o.model_dump(mode="json") for o in list_opportunities(building_id)]


def tool_fdd_results(building_id: str = "", user: Optional[UserContext] = None) -> List[Dict[str, Any]]:
    from app.services.fdd_fault_store import get_fdd_fault_store

    if building_id:
        return get_fdd_fault_store().list_active(building_id)
    return [f.model_dump(mode="json") for f in live_data_service.list_fdd_results(user=user)]


TOOL_REGISTRY: Dict[str, ToolFn] = {
    "building_live": tool_building_live,
    "data_health": tool_data_health,
    "recommendations": tool_recommendations,
    "savings_opportunities": tool_savings_opportunities,
    "fdd_results": tool_fdd_results,
}


async def invoke_tool(tool: str, building_id: str, user: Optional[UserContext] = None) -> Any:
    fn = TOOL_REGISTRY.get(tool)
    if not fn:
        return None
    result = fn(building_id, user)
    if hasattr(result, "__await__"):
        return await result
    return result
