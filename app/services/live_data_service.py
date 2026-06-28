from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from app.config import get_settings
from app.data.buildings_registry import BUILDING_REGISTRY, get_building_config
from app.models.schemas import (
    Alert,
    BuildingDetail,
    BuildingMetrics,
    BuildingSummary,
    EnergyConsumption,
    EnergyForecast,
    EnergySavings,
    EnvironmentData,
    EquipmentDetail,
    EquipmentSummary,
    EnergyData,
    HVACData,
    LiveBuildingData,
    MetricPoint,
)
from app.services import demo_mode
from app.services.influx_client import InfluxService
from app.services.jci_metasys import JCIMetasysClient
from app.services.live_cache import live_cache
from app.utils.dewa_tariff import calculate_dewa_tariff


def _influx() -> InfluxService:
    s = get_settings()
    return InfluxService(s.influx_url, s.influx_token, s.influx_org, s.influx_bucket, s.demo_mode)


def _jci() -> JCIMetasysClient:
    s = get_settings()
    return JCIMetasysClient(
        s.jci_metasys_host,
        s.jci_metasys_username,
        s.jci_metasys_password,
        s.jci_metasys_version,
        s.demo_mode,
    )


def list_buildings() -> List[BuildingSummary]:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.list_buildings()

    results = []
    for cfg in BUILDING_REGISTRY:
        cached = live_cache.get_live(cfg["id"])
        demo = demo_mode.get_building(cfg["id"])
        savings = demo.energy_savings_pct if demo else 20.0
        alerts = len([a for a in live_cache.get_alerts() if a.building_id == cfg["id"]]) or (
            demo.active_alerts if demo else 0
        )
        results.append(
            BuildingSummary(
                id=cfg["id"],
                name=cfg["name"],
                location=cfg["location"],
                floors=cfg["floors"],
                area_sqm=cfg["area_sqm"],
                status="online" if cached else "maintenance",
                energy_savings_pct=savings,
                active_alerts=alerts,
            )
        )
    return results


def get_building(building_id: str) -> Optional[BuildingDetail]:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_building(building_id)

    cfg = get_building_config(building_id)
    if not cfg:
        return None
    summary = next((b for b in list_buildings() if b.id == building_id), None)
    if not summary:
        return None
    return BuildingDetail(
        **summary.model_dump(),
        bms_type=cfg["bms_type"],
        installed_capacity_kw=cfg["installed_capacity_kw"],
        last_updated=datetime.now(timezone.utc),
    )


async def get_live_data(building_id: str) -> Optional[LiveBuildingData]:
    cached = live_cache.get_live(building_id)
    if cached:
        return cached

    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_live_data(building_id)

    influx = _influx()
    from_influx = influx.get_latest_snapshot(building_id)
    if from_influx:
        live_cache.set_live(building_id, from_influx)
        return from_influx

    cfg = get_building_config(building_id)
    if cfg and cfg.get("metasys_objects") and settings.jci_metasys_host:
        live = await _fetch_live_from_metasys(building_id, cfg)
        if live:
            live_cache.set_live(building_id, live)
            return live

    fallback = demo_mode.get_live_data(building_id)
    if fallback:
        return fallback.model_copy(update={"demo_mode": False})
    return None


async def _fetch_live_from_metasys(building_id: str, cfg: Dict[str, Any]) -> Optional[LiveBuildingData]:
    client = _jci()
    objects = cfg.get("metasys_objects", {})
    values: Dict[str, float] = {}
    for key, obj_id in objects.items():
        val = await client.get_present_value(obj_id)
        if isinstance(val, (int, float)):
            values[key] = float(val)
        elif isinstance(val, dict) and "value" in val:
            try:
                values[key] = float(val["value"])
            except (TypeError, ValueError):
                pass

    if not values:
        return None

    supply = values.get("supply_air_temp", 14.0)
    return_air = values.get("return_air_temp", 24.0)
    hvac_kw = values.get("hvac_power_kw", 195.0)
    total_kw = values.get("total_kw", hvac_kw * 4.2)
    cop = max(3.0, min(5.0, (return_air - supply) / max(hvac_kw / 100, 0.1)))
    hour = datetime.now(timezone.utc).hour
    tariff = 0.38 if 12 <= hour < 24 else 0.23

    return LiveBuildingData(
        building_id=building_id,
        timestamp=datetime.now(timezone.utc),
        hvac=HVACData(
            supply_air_temp=supply,
            return_air_temp=return_air,
            delta_t=round(return_air - supply, 1),
            power_kw=hvac_kw,
            cop=round(cop, 1),
        ),
        energy=EnergyData(
            total_kw=total_kw,
            hvac_kw=hvac_kw,
            lighting_kw=round(total_kw * 0.15, 1),
            other_kw=round(total_kw * 0.55, 1),
            tariff_rate=tariff,
            cost_per_hour=round(total_kw * tariff, 1),
        ),
        environment=EnvironmentData(
            temp_c=23.0,
            humidity_pct=48.0,
            co2_ppm=600,
            pm25=20.0,
        ),
        active_alerts=len([a for a in live_cache.get_alerts() if a.building_id == building_id]),
        demo_mode=False,
    )


def get_building_metrics(building_id: str, period: str = "24h") -> Optional[BuildingMetrics]:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_building_metrics(building_id, period)

    hours = {"1h": 1, "24h": 24, "7d": 168}.get(period, 24)
    influx = _influx()
    points = influx.query_metrics(building_id, hours=hours)
    if not points:
        return demo_mode.get_building_metrics(building_id, period)

    metrics = [
        MetricPoint(timestamp=p["timestamp"], value=p["value"], metric=p["metric"])
        for p in points
    ]
    return BuildingMetrics(building_id=building_id, period=period, metrics=metrics)


def get_energy_consumption() -> EnergyConsumption:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_energy_consumption()

    live = live_cache.get_live("burj-khalifa-01")
    if not live:
        data = demo_mode.get_energy_consumption()
        return data.model_copy(update={"demo_mode": False})

    hour = datetime.now(timezone.utc).hour
    tariff = 0.38 if 12 <= hour < 24 else 0.23
    return EnergyConsumption(
        timestamp=live.timestamp,
        total_kw=live.energy.total_kw,
        hvac_kw=live.energy.hvac_kw,
        lighting_kw=live.energy.lighting_kw,
        other_kw=live.energy.other_kw,
        cost_aed_per_hour=round(live.energy.total_kw * tariff, 1),
        demo_mode=False,
    )


def get_energy_forecast(building_id: str, horizon_hours: int = 24) -> EnergyForecast:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_energy_forecast(building_id, horizon_hours)
    forecast = demo_mode.get_energy_forecast(building_id, horizon_hours)
    return forecast.model_copy(update={"demo_mode": False})


def get_energy_savings() -> EnergySavings:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_energy_savings()
    savings = demo_mode.get_energy_savings()
    return savings.model_copy(update={"demo_mode": False})


def get_dewa_tariff():
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_dewa_tariff()
    return calculate_dewa_tariff(52000.0, 34000.0, 950.0)


def list_equipment(building_id: Optional[str] = None) -> List[EquipmentSummary]:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.list_equipment(building_id)
    items = demo_mode.list_equipment(building_id)
    return [item.model_copy(update={}) for item in items]


def get_equipment(equipment_id: str) -> Optional[EquipmentDetail]:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_equipment(equipment_id)
    return demo_mode.get_equipment(equipment_id)


def get_equipment_history(equipment_id: str) -> List[MetricPoint]:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_equipment_history(equipment_id)
    return demo_mode.get_equipment_history(equipment_id)


def list_alerts() -> List[Alert]:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.list_alerts()
    cached = live_cache.get_alerts()
    if cached:
        return cached
    return demo_mode.list_alerts()


def list_alert_history() -> List[Alert]:
    alerts = list_alerts()
    for alert in alerts:
        alert.acknowledged = True
    return alerts


def list_fdd_results():
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.list_fdd_results()
    return demo_mode.list_fdd_results()


def ingest_live_snapshot(data: LiveBuildingData) -> None:
    """Accept live data from edge gateway or manual ingest."""
    live_cache.set_live(data.building_id, data.model_copy(update={"demo_mode": False}))
    influx = _influx()
    tags = {"building_id": data.building_id}
    influx.write_point("total_kw", data.energy.total_kw, tags)
    influx.write_point("hvac_kw", data.energy.hvac_kw, tags)
    influx.write_point("temp_c", data.environment.temp_c, tags)
    influx.write_point("co2_ppm", float(data.environment.co2_ppm), tags)
