"""AI assistant tools — query real building data only."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Union

from app.services import live_data_service
from app.services.data_health_engine import building_data_health
from app.services.metasys_object_store import get_metasys_objects
from app.services.recommendations_store import list_recommendations
from app.services.savings_engine import list_opportunities

ToolFn = Union[
    Callable[[str], Any],
    Callable[[str], Awaitable[Any]],
    Callable[[], Any],
]


async def tool_building_live(building_id: str) -> Dict[str, Any]:
    live = await live_data_service.get_live_data(building_id)
    if not live:
        return {"available": False, "reason": "NO_TELEMETRY", "building_id": building_id}
    return {"available": True, "data": live.model_dump(mode="json"), "source": live.source}


async def tool_data_health(building_id: str) -> Dict[str, Any]:
    mapped = get_metasys_objects(building_id) or {}
    live = await live_data_service.get_live_data(building_id)
    if not live:
        return {"available": False, "reason": "NO_TELEMETRY"}
    values = {
        "supply_air_temp": live.hvac.supply_air_temp,
        "return_air_temp": live.hvac.return_air_temp,
        "hvac_power_kw": live.hvac.power_kw,
        "total_kw": live.energy.total_kw,
        "temp_c": live.environment.temp_c,
        "co2_ppm": live.environment.co2_ppm,
    }
    return {"available": True, "health": building_data_health(mapped, values, observed_at=live.timestamp)}


def tool_recommendations(building_id: str) -> List[Dict[str, Any]]:
    return [r.model_dump(mode="json") for r in list_recommendations(building_id)]


def tool_savings_opportunities(building_id: str) -> List[Dict[str, Any]]:
    return [o.model_dump(mode="json") for o in list_opportunities(building_id)]


def tool_fdd_results(_building_id: str = "") -> List[Dict[str, Any]]:
    return [f.model_dump(mode="json") for f in live_data_service.list_fdd_results()]


TOOL_REGISTRY: Dict[str, ToolFn] = {
    "building_live": tool_building_live,
    "data_health": tool_data_health,
    "recommendations": tool_recommendations,
    "savings_opportunities": tool_savings_opportunities,
    "fdd_results": tool_fdd_results,
}


async def invoke_tool(tool: str, building_id: str) -> Any:
    fn = TOOL_REGISTRY.get(tool)
    if not fn:
        return None
    if tool == "fdd_results":
        return fn(building_id)
    result = fn(building_id)
    if hasattr(result, "__await__"):
        return await result
    return result
