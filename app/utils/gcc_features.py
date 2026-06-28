from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from app.config import get_settings
from app.models.schemas import PrayerTimes, RamadanMode, SandstormAlert


PRAYER_HVAC_ADJUSTMENTS = [
    {"prayer": "dhuhr", "action": "reduce_setpoint", "value": 20, "duration_min": 15},
    {"prayer": "asr", "action": "reduce_setpoint", "value": 20, "duration_min": 15},
    {"prayer": "maghrib", "action": "reduce_setpoint", "value": 20, "duration_min": 15},
    {"prayer": "isha", "action": "reduce_setpoint", "value": 20, "duration_min": 15},
]

DEFAULT_PRAYER_TIMES = {
    "fajr": "05:23",
    "sunrise": "06:42",
    "dhuhr": "12:14",
    "asr": "15:24",
    "maghrib": "17:47",
    "isha": "19:07",
}


async def get_prayer_times() -> PrayerTimes:
    settings = get_settings()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if settings.demo_mode or not settings.latitude:
        return PrayerTimes(
            date=today,
            location="Dubai, UAE",
            times=DEFAULT_PRAYER_TIMES,
            hvac_adjustments=PRAYER_HVAC_ADJUSTMENTS,
        )

    url = (
        f"http://api.aladhan.com/v1/timings/{today}"
        f"?latitude={settings.latitude}&longitude={settings.longitude}&method=8"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()["data"]["timings"]
            times = {
                "fajr": data["Fajr"][:5],
                "sunrise": data["Sunrise"][:5],
                "dhuhr": data["Dhuhr"][:5],
                "asr": data["Asr"][:5],
                "maghrib": data["Maghrib"][:5],
                "isha": data["Isha"][:5],
            }
    except Exception:
        times = DEFAULT_PRAYER_TIMES

    return PrayerTimes(
        date=today,
        location="Dubai, UAE",
        times=times,
        hvac_adjustments=PRAYER_HVAC_ADJUSTMENTS,
    )


def get_ramadan_mode() -> RamadanMode:
    now = datetime.now(timezone.utc)
    # Simplified Hijri approximation for demo purposes
    hijri_month = ((now.month + 8) % 12) + 1
    active = hijri_month == 9
    schedule: List[Dict[str, Any]] = [
        {"event": "iftar", "action": "reduce_setpoint", "value": 20, "offset_min": -30},
        {"event": "suhoor", "action": "maintain_setpoint", "value": 22},
        {"event": "night", "action": "increase_ventilation", "value": 15},
    ]
    return RamadanMode(active=active, hijri_date=f"1446-{hijri_month:02d}-15", schedule=schedule)


async def get_sandstorm_alert() -> SandstormAlert:
    settings = get_settings()
    threshold = 500.0
    pm10 = 120.0 if settings.demo_mode else 120.0
    active = pm10 > threshold
    actions = []
    if active:
        actions = [
            "Switch AHUs to recirculation mode",
            "Close outdoor air dampers",
            "Alert maintenance team",
            "Log sandstorm event",
        ]
    return SandstormAlert(
        active=active,
        pm10=pm10,
        threshold=threshold,
        actions=actions,
        timestamp=datetime.now(timezone.utc),
    )


async def adjust_hvac_for_prayer(prayer: str) -> Dict[str, Any]:
    valid = {item["prayer"] for item in PRAYER_HVAC_ADJUSTMENTS}
    if prayer not in valid:
        return {
            "success": False,
            "message": {"en": "Unknown prayer", "ar": "صلاة غير معروفة"},
        }
    adjustment = next(item for item in PRAYER_HVAC_ADJUSTMENTS if item["prayer"] == prayer)
    return {
        "success": True,
        "prayer": prayer,
        "adjustment": adjustment,
        "message": {
            "en": f"HVAC adjusted for {prayer}",
            "ar": f"تم ضبط التكييف لصلاة {prayer}",
        },
    }
