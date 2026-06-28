"""Simulated building data matching frontend simulationEngine.ts ranges."""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.models.schemas import (
    Alert,
    BuildingDetail,
    BuildingMetrics,
    BuildingSummary,
    DewaTariffBreakdown,
    DewaTariffResponse,
    EnergyConsumption,
    EnergyForecast,
    EnergyForecastPoint,
    EnergySavings,
    EnvironmentData,
    EquipmentDetail,
    EquipmentSummary,
    EnergyData,
    FDDResult,
    HVACData,
    LiveBuildingData,
    MetricPoint,
)

BUILDINGS = [
    {
        "id": "burj-khalifa-01",
        "name": "Burj Khalifa Tower A",
        "location": "Downtown Dubai, UAE",
        "floors": 163,
        "area_sqm": 309473.0,
        "bms_type": "Johnson Controls Metasys",
        "installed_capacity_kw": 5200.0,
    },
    {
        "id": "dubai-mall-01",
        "name": "Dubai Mall Central Plant",
        "location": "Downtown Dubai, UAE",
        "floors": 4,
        "area_sqm": 502000.0,
        "bms_type": "Johnson Controls OpenBlue",
        "installed_capacity_kw": 8400.0,
    },
    {
        "id": "difc-gate-01",
        "name": "DIFC Gate Building",
        "location": "DIFC, Dubai, UAE",
        "floors": 15,
        "area_sqm": 45000.0,
        "bms_type": "Honeywell Niagara",
        "installed_capacity_kw": 1200.0,
    },
]

EQUIPMENT = [
    {"id": "chiller-01", "name": "Chiller Plant 1", "type": "chiller", "building_id": "burj-khalifa-01"},
    {"id": "ahu-01", "name": "AHU Level 42", "type": "ahu", "building_id": "burj-khalifa-01"},
    {"id": "vav-01", "name": "VAV Zone 12A", "type": "vav", "building_id": "burj-khalifa-01"},
    {"id": "chiller-02", "name": "Chiller Plant 2", "type": "chiller", "building_id": "dubai-mall-01"},
    {"id": "ahu-02", "name": "AHU Retail Block", "type": "ahu", "building_id": "dubai-mall-01"},
    {"id": "fcu-01", "name": "FCU Office 5", "type": "fcu", "building_id": "difc-gate-01"},
]


def _seed_for(key: str) -> random.Random:
    digest = hashlib.md5(key.encode()).hexdigest()
    return random.Random(int(digest[:8], 16))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _range(rng: random.Random, low: float, high: float, decimals: int = 1) -> float:
    value = rng.uniform(low, high)
    return round(value, decimals)


def list_buildings() -> List[BuildingSummary]:
    results = []
    for building in BUILDINGS:
        rng = _seed_for(building["id"])
        results.append(
            BuildingSummary(
                id=building["id"],
                name=building["name"],
                location=building["location"],
                floors=building["floors"],
                area_sqm=building["area_sqm"],
                status="online",
                energy_savings_pct=_range(rng, 18.0, 23.0),
                active_alerts=rng.randint(2, 5),
            )
        )
    return results


def get_building(building_id: str) -> Optional[BuildingDetail]:
    building = next((b for b in BUILDINGS if b["id"] == building_id), None)
    if not building:
        return None
    rng = _seed_for(building_id)
    return BuildingDetail(
        id=building["id"],
        name=building["name"],
        location=building["location"],
        floors=building["floors"],
        area_sqm=building["area_sqm"],
        status="online",
        energy_savings_pct=_range(rng, 18.0, 23.0),
        active_alerts=rng.randint(2, 5),
        bms_type=building["bms_type"],
        installed_capacity_kw=building["installed_capacity_kw"],
        last_updated=_now(),
    )


def get_live_data(building_id: str) -> Optional[LiveBuildingData]:
    if not get_building(building_id):
        return None

    rng = _seed_for(f"{building_id}-live-{_now().strftime('%Y%m%d%H%M')}")
    hvac_kw = _range(rng, 180.0, 220.0)
    cop = _range(rng, 3.2, 4.1)
    supply = _range(rng, 12.5, 15.5)
    return_temp = _range(rng, 23.0, 25.0)
    lighting_kw = _range(rng, 110.0, 140.0)
    other_kw = _range(rng, 480.0, 560.0)
    total_kw = round(hvac_kw + lighting_kw + other_kw, 1)
    tariff_rate = 0.38 if 12 <= _now().hour < 24 else 0.23

    return LiveBuildingData(
        building_id=building_id,
        timestamp=_now(),
        hvac=HVACData(
            supply_air_temp=supply,
            return_air_temp=return_temp,
            delta_t=round(return_temp - supply, 1),
            power_kw=hvac_kw,
            cop=cop,
        ),
        energy=EnergyData(
            total_kw=total_kw,
            hvac_kw=hvac_kw,
            lighting_kw=lighting_kw,
            other_kw=other_kw,
            tariff_rate=tariff_rate,
            cost_per_hour=round(total_kw * tariff_rate, 1),
        ),
        environment=EnvironmentData(
            temp_c=_range(rng, 22.0, 24.0),
            humidity_pct=_range(rng, 42.0, 55.0),
            co2_ppm=rng.randint(400, 800),
            pm25=_range(rng, 12.0, 35.0),
        ),
        active_alerts=rng.randint(2, 5),
        demo_mode=True,
    )


def get_building_metrics(building_id: str, period: str = "24h") -> Optional[BuildingMetrics]:
    if not get_building(building_id):
        return None

    rng = _seed_for(f"{building_id}-{period}")
    hours = {"1h": 1, "24h": 24, "7d": 168}.get(period, 24)
    step = max(1, hours // 24)
    metrics: List[MetricPoint] = []
    now = _now()
    for i in range(0, hours, step):
        ts = now - timedelta(hours=hours - i)
        metrics.append(MetricPoint(timestamp=ts, value=_range(rng, 700.0, 950.0), metric="total_kw"))
        metrics.append(MetricPoint(timestamp=ts, value=_range(rng, 180.0, 220.0), metric="hvac_kw"))
        metrics.append(MetricPoint(timestamp=ts, value=_range(rng, 22.0, 24.0), metric="temp_c"))
    return BuildingMetrics(building_id=building_id, period=period, metrics=metrics)


def get_energy_consumption() -> EnergyConsumption:
    rng = _seed_for(f"energy-{_now().strftime('%Y%m%d%H')}")
    hvac_kw = _range(rng, 180.0, 220.0)
    lighting_kw = _range(rng, 110.0, 140.0)
    other_kw = _range(rng, 480.0, 560.0)
    total_kw = round(hvac_kw + lighting_kw + other_kw, 1)
    tariff = 0.38 if 12 <= _now().hour < 24 else 0.23
    return EnergyConsumption(
        timestamp=_now(),
        total_kw=total_kw,
        hvac_kw=hvac_kw,
        lighting_kw=lighting_kw,
        other_kw=other_kw,
        cost_aed_per_hour=round(total_kw * tariff, 1),
        demo_mode=True,
    )


def get_energy_forecast(building_id: str, horizon_hours: int = 24) -> EnergyForecast:
    rng = _seed_for(f"forecast-{building_id}")
    now = _now()
    forecast = []
    base = _range(rng, 750.0, 900.0)
    for hour in range(1, horizon_hours + 1):
        ts = now + timedelta(hours=hour)
        predicted = base + _range(rng, -80.0, 80.0)
        forecast.append(
            EnergyForecastPoint(
                timestamp=ts,
                predicted_kw=predicted,
                confidence=_range(rng, 0.82, 0.95, 2),
            )
        )
    return EnergyForecast(
        building_id=building_id,
        horizon_hours=horizon_hours,
        forecast=forecast,
        demo_mode=True,
    )


def get_dewa_tariff() -> DewaTariffResponse:
    rng = _seed_for(f"dewa-{_now().strftime('%Y%m')}")
    month_num = _now().month
    is_summer = 5 <= month_num <= 10
    peak_kwh = _range(rng, 45000.0, 62000.0, 0)
    off_peak_kwh = _range(rng, 28000.0, 38000.0, 0)
    peak_rate = 0.38 if is_summer else 0.23
    off_peak_rate = 0.23
    peak_cost = round(peak_kwh * peak_rate, 2)
    off_peak_cost = round(off_peak_kwh * off_peak_rate, 2)
    demand_charge = 30.0 * _range(rng, 800.0, 1200.0, 0)
    return DewaTariffResponse(
        month=_now().strftime("%Y-%m"),
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
        demo_mode=True,
    )


def get_energy_savings() -> EnergySavings:
    rng = _seed_for("savings")
    baseline = _range(rng, 95000.0, 110000.0, 0)
    savings_pct = _range(rng, 18.0, 23.0)
    actual = round(baseline * (1 - savings_pct / 100), 0)
    savings_kwh = baseline - actual
    return EnergySavings(
        baseline_kwh=baseline,
        actual_kwh=actual,
        savings_kwh=savings_kwh,
        savings_pct=savings_pct,
        cost_saved_aed=round(savings_kwh * 0.30, 2),
        demo_mode=True,
    )


def list_equipment(building_id: Optional[str] = None) -> List[EquipmentSummary]:
    items = EQUIPMENT if not building_id else [e for e in EQUIPMENT if e["building_id"] == building_id]
    results = []
    for item in items:
        rng = _seed_for(item["id"])
        status = rng.choice(["running", "running", "running", "maintenance"])
        results.append(
            EquipmentSummary(
                id=item["id"],
                name=item["name"],
                type=item["type"],
                building_id=item["building_id"],
                status=status,
                power_kw=_range(rng, 45.0, 320.0),
                efficiency=_range(rng, 0.78, 0.94, 2),
            )
        )
    return results


def get_equipment(equipment_id: str) -> Optional[EquipmentDetail]:
    item = next((e for e in EQUIPMENT if e["id"] == equipment_id), None)
    if not item:
        return None
    rng = _seed_for(equipment_id)
    setpoint = _range(rng, 6.0, 24.0)
    return EquipmentDetail(
        id=item["id"],
        name=item["name"],
        type=item["type"],
        building_id=item["building_id"],
        status=rng.choice(["running", "running", "fault"]),
        power_kw=_range(rng, 45.0, 320.0),
        efficiency=_range(rng, 0.78, 0.94, 2),
        setpoint=setpoint,
        current_value=round(setpoint + _range(rng, -1.5, 1.5), 1),
        last_maintenance=_now() - timedelta(days=rng.randint(10, 90)),
        fault_code=None if rng.random() > 0.2 else "FDD-023",
    )


def get_equipment_history(equipment_id: str) -> List[MetricPoint]:
    if not get_equipment(equipment_id):
        return []
    rng = _seed_for(f"{equipment_id}-history")
    now = _now()
    return [
        MetricPoint(
            timestamp=now - timedelta(hours=i),
            value=_range(rng, 40.0, 300.0),
            metric="power_kw",
        )
        for i in range(24, 0, -1)
    ]


def list_alerts() -> List[Alert]:
    rng = _seed_for("alerts")
    templates = [
        ("critical", "HVAC", "Supply Air Temp Deviation", "Supply air temperature exceeds setpoint by 3°C", "درجة حرارة هواء التغذية تتجاوز نقطة الضبط"),
        ("warning", "Chiller", "COP Degradation", "Chiller COP below 3.0 threshold", "معامل الأداء COP للمبرد أقل من 3.0"),
        ("warning", "AHU", "Filter Pressure Drop", "Filter pressure drop exceeds 250 Pa", "انخفاض ضغط الفلتر يتجاوز 250 باسكال"),
        ("info", "Energy", "Peak Demand Spike", "Peak demand 12% above baseline", "ذروة الطلب أعلى من خط الأساس بنسبة 12%"),
        ("critical", "BMS", "Communication Loss", "BACnet point communication timeout", "انقطاع اتصال نقطة BACnet"),
    ]
    alerts = []
    for idx, (severity, category, title, message, message_ar) in enumerate(templates[: rng.randint(3, 5)]):
        alerts.append(
            Alert(
                id=f"alert-{idx + 1:03d}",
                building_id=rng.choice([b["id"] for b in BUILDINGS]),
                equipment_id=rng.choice([e["id"] for e in EQUIPMENT]),
                severity=severity,
                category=category,
                title=title,
                message=message,
                message_ar=message_ar,
                timestamp=_now() - timedelta(minutes=rng.randint(5, 480)),
                acknowledged=False,
            )
        )
    return alerts


def list_alert_history() -> List[Alert]:
    history = list_alerts()
    for alert in history:
        alert.acknowledged = True
    return history


def list_fdd_results() -> List[FDDResult]:
    rng = _seed_for("fdd")
    rules = [
        ("FDD-001", "HVAC", "Supply air temp deviation > 2°C"),
        ("FDD-007", "Chiller", "COP degradation below 3.0"),
        ("FDD-012", "AHU", "Filter pressure drop > 250 Pa"),
        ("FDD-019", "Energy", "Baseline deviation > 15%"),
        ("FDD-031", "BMS", "Sensor stuck / no variance"),
    ]
    results = []
    for rule_id, category, description in rules:
        results.append(
            FDDResult(
                rule_id=rule_id,
                category=category,
                equipment_id=rng.choice([e["id"] for e in EQUIPMENT]),
                severity=rng.choice(["critical", "warning", "info"]),
                description=description,
                description_ar="نتيجة كشف عطل محاكاة",
                confidence=_range(rng, 0.75, 0.98, 2),
                detected_at=_now() - timedelta(minutes=rng.randint(10, 600)),
            )
        )
    return results


def get_jci_objects() -> List[Dict[str, Any]]:
    return [
        {"id": "obj-1001", "name": "CHW-Supply-Temp", "type": "Analog Input", "present_value": 6.8},
        {"id": "obj-1002", "name": "CHW-Return-Temp", "type": "Analog Input", "present_value": 12.4},
        {"id": "obj-2001", "name": "Chiller-Enable", "type": "Binary Output", "present_value": True},
        {"id": "obj-3001", "name": "OA-Damper-Cmd", "type": "Analog Output", "present_value": 45.0},
    ]


def get_jci_alarms() -> List[Dict[str, Any]]:
    return [
        {
            "id": "alm-001",
            "object_id": "obj-1001",
            "priority": "high",
            "message": "CHW supply temperature high",
            "timestamp": _now().isoformat(),
        }
    ]


def get_jci_trend(object_id: str) -> List[Dict[str, Any]]:
    rng = _seed_for(f"jci-trend-{object_id}")
    now = _now()
    return [
        {"timestamp": (now - timedelta(minutes=i * 5)).isoformat(), "value": _range(rng, 5.0, 15.0)}
        for i in range(24)
    ]
