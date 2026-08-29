"""Reports, optimization shadow, writeback status APIs."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.deps.auth import UserContext
from app.deps.guards import assert_building_access, require_module_enabled
from app.services.report_service import building_performance_report, executive_pilot_report, fdd_report
from app.services.shadow_optimization_engine import shadow_optimize
from app.services.writeback_service import writeback_status

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/buildings/{building_id}/performance")
async def get_performance_report(
    building_id: str,
    hours: int = Query(default=168, le=168),
    user: UserContext = Depends(require_module_enabled("overview")),
) -> dict:
    assert_building_access(user, building_id)
    return building_performance_report(building_id, hours=hours)


@router.get("/buildings/{building_id}/fdd")
async def get_fdd_report(
    building_id: str,
    user: UserContext = Depends(require_module_enabled("fdd")),
) -> dict:
    assert_building_access(user, building_id)
    return fdd_report(building_id)


@router.get("/buildings/{building_id}/executive")
async def get_executive_report(
    building_id: str,
    user: UserContext = Depends(require_module_enabled("executive")),
) -> dict:
    assert_building_access(user, building_id)
    return executive_pilot_report(building_id)


@router.get("/buildings/{building_id}/shadow-optimization")
async def get_shadow_optimization(
    building_id: str,
    user: UserContext = Depends(require_module_enabled("optimization")),
) -> dict:
    assert_building_access(user, building_id)
    return shadow_optimize(
        building_id=building_id,
        current_setpoints={"supply_air_setpoint": 21.0, "chws_setpoint": 6.5},
        constraints={"min_supply_temp": 18, "max_chws_temp": 8, "max_supply_temp": 24},
    )


@router.get("/writeback/status")
async def get_writeback_status(
    site_id: Optional[str] = None,
    user: UserContext = Depends(require_module_enabled("settings")),
) -> dict:
    return writeback_status(site_id)
