from fastapi import APIRouter, Query

from app.models.schemas import (
    DewaTariffResponse,
    EnergyConsumption,
    EnergyForecast,
    EnergySavings,
)
from app.services import demo_mode
from app.utils.dewa_tariff import calculate_dewa_tariff

router = APIRouter(prefix="/energy", tags=["energy"])


@router.get("/consumption", response_model=EnergyConsumption)
async def get_consumption() -> EnergyConsumption:
    return demo_mode.get_energy_consumption()


@router.get("/forecast", response_model=EnergyForecast)
async def get_forecast(
    building_id: str = Query(default="burj-khalifa-01"),
    horizon_hours: int = Query(default=24, ge=1, le=168),
) -> EnergyForecast:
    return demo_mode.get_energy_forecast(building_id, horizon_hours)


@router.get("/dewa-tariff", response_model=DewaTariffResponse)
async def get_dewa_tariff(
    peak_kwh: float = Query(default=52000.0, ge=0),
    off_peak_kwh: float = Query(default=34000.0, ge=0),
    demand_kva: float = Query(default=950.0, ge=0),
) -> DewaTariffResponse:
    return calculate_dewa_tariff(peak_kwh=peak_kwh, off_peak_kwh=off_peak_kwh, demand_kva=demand_kva)


@router.get("/savings", response_model=EnergySavings)
async def get_savings() -> EnergySavings:
    return demo_mode.get_energy_savings()
