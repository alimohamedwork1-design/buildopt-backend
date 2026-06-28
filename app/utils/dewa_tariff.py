from datetime import datetime, timezone
from typing import Dict

from app.models.schemas import DewaTariffBreakdown, DewaTariffResponse


SUMMER_MONTHS = {5, 6, 7, 8, 9, 10}
PEAK_RATE_SUMMER = 0.38
OFF_PEAK_RATE = 0.23
DEMAND_CHARGE_PER_KVA = 30.0


def calculate_dewa_tariff(
    peak_kwh: float,
    off_peak_kwh: float,
    demand_kva: float,
    when: datetime | None = None,
) -> DewaTariffResponse:
    now = when or datetime.now(timezone.utc)
    is_summer = now.month in SUMMER_MONTHS
    peak_rate = PEAK_RATE_SUMMER if is_summer else OFF_PEAK_RATE
    off_peak_rate = OFF_PEAK_RATE

    peak_cost = round(peak_kwh * peak_rate, 2)
    off_peak_cost = round(off_peak_kwh * off_peak_rate, 2)
    demand_charge = round(demand_kva * DEMAND_CHARGE_PER_KVA, 2)

    return DewaTariffResponse(
        month=now.strftime("%Y-%m"),
        is_summer=is_summer,
        peak=DewaTariffBreakdown(
            period="12:00-24:00" if is_summer else "flat",
            rate_aed_per_kwh=peak_rate,
            consumption_kwh=peak_kwh,
            cost_aed=peak_cost,
        ),
        off_peak=DewaTariffBreakdown(
            period="00:00-12:00" if is_summer else "flat",
            rate_aed_per_kwh=off_peak_rate,
            consumption_kwh=off_peak_kwh,
            cost_aed=off_peak_cost,
        ),
        demand_charge_aed=demand_charge,
        total_cost_aed=round(peak_cost + off_peak_cost + demand_charge, 2),
        demo_mode=False,
    )
