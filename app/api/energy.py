from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps.auth import UserContext, get_optional_user
from app.deps.guards import assert_building_access, empty_no_building, require_module_enabled
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
    if user.is_live_account:
        data = await live_data_service.get_live_data(building_id, user=user)
        if not data:
            raise HTTPException(status_code=503, detail={"code": "NOT_CONFIGURED"})
    return live_data_service.get_energy_consumption()


@router.get("/forecast", response_model=EnergyForecast)
async def get_forecast(
    building_id: str = Query(default="burj-khalifa-01"),
    horizon_hours: int = Query(default=24, ge=1, le=168),
    user: UserContext = Depends(require_module_enabled("energy")),
) -> EnergyForecast:
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    assert_building_access(user, building_id)
    return live_data_service.get_energy_forecast(building_id, horizon_hours)


@router.get("/dewa-tariff", response_model=DewaTariffResponse)
async def get_dewa_tariff(
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

    settings = get_settings()
    if user.allows_demo_data() and settings.demo_mode:
        return demo_mode.get_dewa_tariff()
    return calculate_dewa_tariff(peak_kwh=peak_kwh, off_peak_kwh=off_peak_kwh, demand_kva=demand_kva)


@router.get("/savings", response_model=EnergySavings)
async def get_savings(
    user: UserContext = Depends(require_module_enabled("energy")),
) -> EnergySavings:
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    return live_data_service.get_energy_savings()
