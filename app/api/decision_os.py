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
from app.services.decision_advanced import (
    TariffProfileRequest, RefrigerationAdvisoryRequest,
    analyze_tariff_profile, review_refrigeration_staging,
)
from app.services.decision_measurement_review import MeasurementReviewRequest, prepare_mv_review

router = APIRouter(prefix="/decision-os", tags=["decision-os"])


@router.get("/catalog")
async def decision_catalog() -> dict:
    return {
        "product": "BuildOpt Decision OS",
        "version": "2.0-illustrative",
        "state": "engineering_review_only",
        "engines": [
            {"id": "chiller_dispatch", "description": "Bounded on/off subset optimization using stated COP assumptions"},
            {"id": "hvac_scheduling", "description": "Daily run-hour comparison with occupancy/preconditioning constraint"},
            {"id": "fault_prioritization", "description": "Safety-first ordinal engineering review queue"},
            {"id": "tou_energy_cost", "description": "24-hour hourly tariff and demand-charge proxy comparison"},
            {"id": "industrial_cooling_advisory", "description": "Safety-gated hypothetical industrial compressor staging, never PLC control"},
            {"id": "baseline_mv_review", "description": "Operator-provided CDD/runtime baseline regression for independent review, never certified savings"},
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


@router.post("/scenarios/tou-energy-cost")
async def evaluate_tou_energy(
    payload: TariffProfileRequest,
    user: UserContext = Depends(get_required_user),
) -> dict:
    require_assigned_building(user, payload.building_id)
    return analyze_tariff_profile(payload)


@router.post("/scenarios/industrial-cooling-advisory")
async def evaluate_industrial_cooling(
    payload: RefrigerationAdvisoryRequest,
    user: UserContext = Depends(get_required_user),
) -> dict:
    require_assigned_building(user, payload.building_id)
    return review_refrigeration_staging(payload)


@router.post("/scenarios/baseline-mv-review")
async def evaluate_baseline_mv(
    payload: MeasurementReviewRequest,
    user: UserContext = Depends(get_required_user),
) -> dict:
    require_assigned_building(user, payload.building_id)
    return prepare_mv_review(payload)
