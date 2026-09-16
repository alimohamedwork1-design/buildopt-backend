"""Reports, pilot readiness, shadow optimization and writeback status APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.deps.auth import UserContext
from app.deps.guards import assert_building_access, require_module_enabled
from app.services.pilot_os_service import build_pilot_summary
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


@router.get("/buildings/{building_id}/pilot")
async def get_pilot_report(
    building_id: str,
    user: UserContext = Depends(require_module_enabled("overview")),
) -> dict:
    """Evidence-backed pilot report suitable for weekly/monthly export by the frontend."""
    assert_building_access(user, building_id)
    summary = await build_pilot_summary(user, building_id)
    return {
        "report_type": "pilot_readiness",
        "building_id": building_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "state": summary["state"],
        "readiness_score": summary["readiness_score"],
        "readiness_steps": summary["steps"],
        "blockers": summary["blockers"],
        "data_health": summary["data_health"].get("building_summary", {}),
        "connections": summary["connections"],
        "fdd_rule_packs": summary["rule_packs"],
        "operations": summary["operations"],
        "models": summary["models"],
        "safety": summary["safety"],
        "limitations": [
            "Forecast and FDD accuracy require site-specific validation.",
            "Savings are claims only when the M&V lifecycle reaches VERIFIED.",
            "Optimization is shadow-only; automatic BMS writeback is disabled.",
        ],
    }


@router.get("/buildings/{building_id}/shadow-optimization")
async def get_shadow_optimization(
    building_id: str,
    user: UserContext = Depends(require_module_enabled("optimization")),
) -> dict:
    assert_building_access(user, building_id)
    # Do not invent control setpoints. Until mapped control points are explicitly
    # approved, shadow optimization returns no candidates and explains the blocker.
    return shadow_optimize(
        building_id=building_id,
        current_setpoints={},
        constraints={"min_supply_temp": 18, "max_chws_temp": 8, "max_supply_temp": 24},
    )


@router.get("/writeback/status")
async def get_writeback_status(
    site_id: Optional[str] = None,
    user: UserContext = Depends(require_module_enabled("settings")),
) -> dict:
    return writeback_status(site_id)
