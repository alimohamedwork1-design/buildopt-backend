from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps.auth import UserContext
from app.deps.guards import assert_building_access, empty_no_building, require_module_enabled
from app.models.errors import ErrorCode, api_error
from app.models.schemas import DewaTariffResponse, EnergyConsumption, EnergyForecast, EnergySavings
from app.services import live_data_service

router = APIRouter(prefix="/energy", tags=["energy"])


@router.get("/consumption", response_model=EnergyConsumption)
async def get_consumption(
    building_id: str = Query(default="burj-khalifa-01"),
    user: UserContext = Depends(require_module_enabled("energy")),
) -> EnergyConsumption:
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    assert_building_access(user, building_id)
    result = live_data_service.get_energy_consumption(building_id, user=user)
    if result is None:
        raise api_error(
            ErrorCode.NO_TELEMETRY,
            "No energy telemetry available for this building",
            "لا تتوفر بيانات الطاقة لهذا المبنى",
            status_code=503,
        )
    return result


@router.get("/forecast", response_model=EnergyForecast)
async def get_forecast(
    building_id: str = Query(default="burj-khalifa-01"),
    horizon_hours: int = Query(default=24, ge=1, le=168),
    user: UserContext = Depends(require_module_enabled("energy")),
) -> EnergyForecast:
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    assert_building_access(user, building_id)
    result = live_data_service.get_energy_forecast(building_id, horizon_hours, user=user)
    if result is None:
        raise api_error(
            ErrorCode.NO_TELEMETRY,
            "Insufficient history for energy forecast",
            "لا يوجد سجل كافٍ لتوقع الطاقة",
            status_code=503,
        )
    return result


@router.get("/dewa-tariff", response_model=DewaTariffResponse)
async def get_dewa_tariff(
    building_id: str = Query(default="burj-khalifa-01"),
    peak_kwh: float = Query(default=52000.0, ge=0),
    off_peak_kwh: float = Query(default=34000.0, ge=0),
    demand_kva: float = Query(default=950.0, ge=0),
    user: UserContext = Depends(require_module_enabled("energy")),
) -> DewaTariffResponse:
    from app.config import get_settings
    from app.services import demo_mode
    from app.utils.dewa_tariff import calculate_dewa_tariff

    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    assert_building_access(user, building_id)

    settings = get_settings()
    if user.allows_demo_data() and settings.demo_mode:
        return demo_mode.get_dewa_tariff()

    computed = live_data_service.get_dewa_tariff(building_id, user=user)
    if computed:
        return computed
    return calculate_dewa_tariff(peak_kwh=peak_kwh, off_peak_kwh=off_peak_kwh, demand_kva=demand_kva)


@router.get("/savings", response_model=EnergySavings)
async def get_savings(
    building_id: str = Query(default="burj-khalifa-01"),
    user: UserContext = Depends(require_module_enabled("energy")),
) -> EnergySavings:
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    assert_building_access(user, building_id)
    result = live_data_service.get_energy_savings(building_id, user=user)
    if result is None:
        raise api_error(
            ErrorCode.NO_TELEMETRY,
            "Baseline not available — insufficient metered data",
            "خط الأساس غير متاح — بيانات العداد غير كافية",
            status_code=503,
        )
    return result
