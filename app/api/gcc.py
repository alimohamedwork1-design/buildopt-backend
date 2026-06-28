from fastapi import APIRouter

from app.models.schemas import PrayerTimes, RamadanMode, SandstormAlert
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
