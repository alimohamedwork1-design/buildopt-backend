from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import DewaTariffResponse, EnergyConsumption, EnergyForecast, EnergySavings, MetricPoint
from app.services import live_data_service
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/energy", tags=["energy"])


@router.get("/consumption", response_model=EnergyConsumption)
async def get_consumption() -> EnergyConsumption:
    return live_data_service.get_energy_consumption()


@router.get("/forecast", response_model=EnergyForecast)
async def get_forecast(
    building_id: str = Query(default="burj-khalifa-01"),
    horizon_hours: int = Query(default=24, ge=1, le=168),
) -> EnergyForecast:
    return live_data_service.get_energy_forecast(building_id, horizon_hours)


@router.get("/dewa-tariff", response_model=DewaTariffResponse)
async def get_dewa_tariff(
    peak_kwh: float = Query(default=52000.0, ge=0),
    off_peak_kwh: float = Query(default=34000.0, ge=0),
    demand_kva: float = Query(default=950.0, ge=0),
) -> DewaTariffResponse:
    from app.config import get_settings
    from app.utils.dewa_tariff import calculate_dewa_tariff
    from app.services import demo_mode

    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_dewa_tariff()
    return calculate_dewa_tariff(peak_kwh=peak_kwh, off_peak_kwh=off_peak_kwh, demand_kva=demand_kva)


@router.get("/savings", response_model=EnergySavings)
async def get_savings() -> EnergySavings:
    return live_data_service.get_energy_savings()
