from fastapi import APIRouter, Query
from typing import Optional

from app.models.schemas import PrayerTimes, RamadanMode, SandstormAlert
from app.services.gcc_config import get_calendar, get_carbon_factor, get_tariff, list_tariffs
from app.utils.gcc_features import (
    adjust_hvac_for_prayer,
    get_prayer_times,
    get_ramadan_mode,
    get_sandstorm_alert,
)

router = APIRouter(prefix="/gcc", tags=["gcc"])


@router.get("/prayer-times", response_model=PrayerTimes)
async def prayer_times() -> PrayerTimes:
    return await get_prayer_times()


@router.get("/ramadan-mode", response_model=RamadanMode)
async def ramadan_mode() -> RamadanMode:
    return get_ramadan_mode()


@router.get("/sandstorm-alert", response_model=SandstormAlert)
async def sandstorm_alert() -> SandstormAlert:
    return await get_sandstorm_alert()


@router.post("/hvac-prayer-adjust")
async def hvac_prayer_adjust(prayer: str) -> dict:
    return await adjust_hvac_for_prayer(prayer)


@router.get("/tariffs")
async def gcc_tariffs(region: Optional[str] = Query(default=None)) -> dict:
    return {"tariffs": list_tariffs(region), "note": "Reference configuration — not live tariff claims"}


@router.get("/tariffs/{tariff_id}")
async def gcc_tariff_detail(tariff_id: str) -> dict:
    t = get_tariff(tariff_id)
    if not t:
        return {"available": False, "tariff_id": tariff_id}
    return {"available": True, **t}


@router.get("/carbon/{region}")
async def gcc_carbon(region: str) -> dict:
    factor = get_carbon_factor(region)
    return {"region": region, "kg_co2_per_kwh": factor, "available": factor is not None}


@router.get("/calendar/{calendar_id}")
async def gcc_calendar_config(calendar_id: str = "GCC_STANDARD") -> dict:
    return get_calendar(calendar_id)
