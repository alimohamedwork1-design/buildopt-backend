"""Building-scoped, read-only Decision OS v1 endpoints.

No data persistence, control action, BMS writeback, device credentials or
promised energy savings. All scenario inputs are operator-entered assumptions.
"""
from fastapi import APIRouter, Depends
from app.api.compatibility import require_assigned_building
from app.deps.auth import get_required_user
from app.models.user_context import UserContext
from app.services.decision_engine import (
    ChillerDispatchRequest, ScheduleRequest, FaultPriorityRequest,
    optimize_chiller_dispatch, assess_hvac_schedule, prioritize_faults,
)
from app.services.facility_graph import FacilityGraphRequest, check_facility_graph

router = APIRouter(prefix="/decision-os", tags=["decision-os"])


@router.get("/catalog")
async def decision_catalog() -> dict:
    return {
        "product": "BuildOpt Decision OS",
        "version": "1.0-illustrative",
        "state": "engineering_review_only",
        "engines": [
            {"id": "chiller_dispatch", "description": "Bounded on/off subset optimization using stated COP assumptions"},
            {"id": "hvac_scheduling", "description": "Daily run-hour comparison with occupancy/preconditioning constraint"},
            {"id": "fault_prioritization", "description": "Safety-first ordinal engineering review queue"},
        ],
        "facility_graph": "operator_submitted_mapping_validation_only",
        "inputs": "operator_assumptions_or_synthetic_demo",
        "outputs": "not_verified_savings",
        "can_send_equipment_commands": False,
        "customer_site_certification": False,
    }


@router.post("/graph/validate")
async def validate_graph(
    payload: FacilityGraphRequest,
    user: UserContext = Depends(get_required_user),
) -> dict:
    require_assigned_building(user, payload.building_id)
    return check_facility_graph(payload)


@router.post("/scenarios/chiller-dispatch")
async def calculate_chiller_dispatch(
    payload: ChillerDispatchRequest,
    user: UserContext = Depends(get_required_user),
) -> dict:
    require_assigned_building(user, payload.building_id)
    return optimize_chiller_dispatch(payload)


@router.post("/scenarios/hvac-scheduling")
async def calculate_schedule(
    payload: ScheduleRequest,
    user: UserContext = Depends(get_required_user),
) -> dict:
    require_assigned_building(user, payload.building_id)
    return assess_hvac_schedule(payload)


@router.post("/scenarios/fault-prioritization")
async def calculate_fault_priority(
    payload: FaultPriorityRequest,
    user: UserContext = Depends(get_required_user),
) -> dict:
    require_assigned_building(user, payload.building_id)
    return prioritize_faults(payload)
