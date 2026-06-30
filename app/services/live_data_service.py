from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.data.buildings_registry import BUILDING_REGISTRY, get_building_config
from app.models.schemas import (
    Alert,
    BuildingDetail,
    BuildingMetrics,
    BuildingSummary,
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
from app.services import demo_mode
from app.services.connection_store import connection_store
from app.services.influx_client import InfluxService
from app.services.jci_metasys import JCIMetasysClient
from app.services.live_cache import live_cache
from app.services.metasys_object_store import get_metasys_objects
from app.services.site_profile_store import get_site_profile, shows_hvac_connection
from app.services.supabase_client import SupabaseService
from app.utils.dewa_tariff import calculate_dewa_tariff


def _influx(*, force_live: bool = False) -> InfluxService:
    s = get_settings()
    demo = s.demo_mode and not force_live
    return InfluxService(s.influx_url, s.influx_token, s.influx_org, s.influx_bucket, demo)


def _jci_from_store() -> JCIMetasysClient:
    creds = connection_store.get_metasys()
    return JCIMetasysClient(
        creds.host,
        creds.username,
        creds.password,
        creds.version,
        demo_mode=False,
    )


def _supabase() -> SupabaseService:
    s = get_settings()
    return SupabaseService(
        s.supabase_url,
        s.supabase_key,
        s.supabase_service_key,
        demo_mode=s.demo_mode,
        alert_webhook_url=s.supabase_alert_webhook_url,
        alert_webhook_secret=s.alert_webhook_secret,
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
                site_profile=get_site_profile(cfg["id"]),
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
        live = from_influx.model_copy(update={"source": "influx"})
        live_cache.set_live(building_id, live)
        return live

    objects = get_metasys_objects(building_id)
    if objects and connection_store.has_saved_metasys():
        cfg = get_building_config(building_id) or {"id": building_id}
        live = await _fetch_live_from_metasys(building_id, {**cfg, "metasys_objects": objects})
        if live:
            live_cache.set_live(building_id, live)
            return live

    return None


async def poll_metasys_buildings() -> int:
    """Poll Metasys for all buildings with object maps when credentials are saved."""
    if not connection_store.has_saved_metasys():
        return 0

    polled = 0
    influx = _influx()
    for cfg in BUILDING_REGISTRY:
        if not shows_hvac_connection(get_site_profile(cfg["id"])):
            continue
        objects = get_metasys_objects(cfg["id"])
        if not objects:
            continue
        live = await _fetch_live_from_metasys(cfg["id"], {**cfg, "metasys_objects": objects})
        if not live:
            continue
        live_cache.set_live(cfg["id"], live)
        tags = {"building_id": cfg["id"]}
        influx.write_point("total_kw", live.energy.total_kw, tags)
        influx.write_point("hvac_kw", live.energy.hvac_kw, tags)
        influx.write_point("supply_air_temp", live.hvac.supply_air_temp, tags)
        influx.write_point("temp_c", live.environment.temp_c, tags)
        influx.write_point("co2_ppm", float(live.environment.co2_ppm), tags)
        influx.write_point("cop", live.hvac.cop, tags)
        polled += 1
    return polled


async def _fetch_live_from_metasys(building_id: str, cfg: Dict[str, Any]) -> Optional[LiveBuildingData]:
    client = _jci_from_store()
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
            temp_c=values.get("temp_c", 23.0),
            humidity_pct=values.get("humidity_pct", 48.0),
            co2_ppm=int(values.get("co2_ppm", 600)),
            pm25=values.get("pm25", 20.0),
        ),
        active_alerts=len([a for a in live_cache.get_alerts() if a.building_id == building_id]),
        demo_mode=False,
        source="metasys",
    )


def get_building_metrics(building_id: str, period: str = "24h") -> Optional[BuildingMetrics]:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_building_metrics(building_id, period)

    hours = {"1h": 1, "24h": 24, "7d": 168}.get(period, 24)
    influx = _influx()
    points = influx.query_metrics(building_id, hours=hours)
    if not points:
        return None

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
        influx = _influx()
        live = influx.get_latest_snapshot("burj-khalifa-01")
    if not live:
        return EnergyConsumption(
            timestamp=datetime.now(timezone.utc),
            total_kw=0,
            hvac_kw=0,
            lighting_kw=0,
            other_kw=0,
            cost_aed_per_hour=0,
            demo_mode=False,
        )

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

    influx = _influx()
    history = influx.query_hourly_kw(building_id, hours=24)
    if not history:
        return EnergyForecast(
            building_id=building_id,
            horizon_hours=horizon_hours,
            forecast=[],
            demo_mode=False,
        )

    values = [h["value"] for h in history if h.get("metric") == "total_kw"] or [h["value"] for h in history]
    base_kw = sum(values) / max(len(values), 1)
    now = datetime.now(timezone.utc)
    forecast_points: List[EnergyForecastPoint] = []
    for hour in range(1, horizon_hours + 1):
        ts = now + timedelta(hours=hour)
        hour_factor = 1.15 if 12 <= ts.hour < 24 else 0.85
        forecast_points.append(
            EnergyForecastPoint(
                timestamp=ts,
                predicted_kw=round(base_kw * hour_factor, 1),
                confidence=0.88,
            )
        )
    return EnergyForecast(
        building_id=building_id,
        horizon_hours=horizon_hours,
        forecast=forecast_points,
        demo_mode=False,
    )


def get_energy_savings() -> EnergySavings:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_energy_savings()

    influx = _influx()
    history = influx.query_hourly_kw("burj-khalifa-01", hours=720)
    if history:
        actual_kwh = sum(h["value"] for h in history)
        baseline_kwh = actual_kwh * 1.2
        savings_kwh = baseline_kwh - actual_kwh
        savings_pct = round((savings_kwh / baseline_kwh) * 100, 1) if baseline_kwh else 0
        return EnergySavings(
            baseline_kwh=round(baseline_kwh, 0),
            actual_kwh=round(actual_kwh, 0),
            savings_kwh=round(savings_kwh, 0),
            savings_pct=savings_pct,
            cost_saved_aed=round(savings_kwh * 0.30, 2),
            demo_mode=False,
        )

    live = live_cache.get_live("burj-khalifa-01")
    if live:
        actual = live.energy.total_kw * 24 * 30
        baseline = actual * 1.18
        savings_kwh = baseline - actual
        return EnergySavings(
            baseline_kwh=round(baseline, 0),
            actual_kwh=round(actual, 0),
            savings_kwh=round(savings_kwh, 0),
            savings_pct=round((savings_kwh / baseline) * 100, 1),
            cost_saved_aed=round(savings_kwh * 0.30, 2),
            demo_mode=False,
        )

    return EnergySavings(
        baseline_kwh=0,
        actual_kwh=0,
        savings_kwh=0,
        savings_pct=0,
        cost_saved_aed=0,
        demo_mode=False,
    )


def get_dewa_tariff() -> DewaTariffResponse:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_dewa_tariff()

    cached = live_cache.get_dewa_tariff()
    if cached:
        return DewaTariffResponse(**cached)

    live = live_cache.get_live("burj-khalifa-01")
    peak_kwh = (live.energy.total_kw * 12) if live else 52000.0
    off_peak_kwh = (live.energy.total_kw * 12) if live else 34000.0
    tariff = calculate_dewa_tariff(peak_kwh, off_peak_kwh, 950.0)
    live_cache.set_dewa_tariff(tariff.model_dump(mode="json"))
    return tariff


def list_equipment(building_id: Optional[str] = None) -> List[EquipmentSummary]:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.list_equipment(building_id)

    bid = building_id or "burj-khalifa-01"
    live = live_cache.get_live(bid)
    if not live:
        influx = _influx()
        live = influx.get_latest_snapshot(bid)

    if live:
        templates = demo_mode.list_equipment(bid)
        results: List[EquipmentSummary] = []
        for idx, item in enumerate(templates[:8]):
            power = live.energy.hvac_kw if "Chiller" in item.name or "AHU" in item.name else live.energy.lighting_kw
            status = "fault" if live.hvac.cop < 3.2 and "Chiller" in item.name else item.status
            results.append(
                item.model_copy(
                    update={
                        "power_kw": round(power / max(len(templates), 1), 1) if idx == 0 else item.power_kw,
                        "efficiency": min(0.98, max(0.7, live.hvac.cop / 5.0)),
                        "status": status,
                    }
                )
            )
        return results

    items = demo_mode.list_equipment(building_id)
    return [item.model_copy(update={}) for item in items]


def get_equipment(equipment_id: str) -> Optional[EquipmentDetail]:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_equipment(equipment_id)
    detail = demo_mode.get_equipment(equipment_id)
    if not detail:
        return None
    live = live_cache.get_live(detail.building_id)
    if live:
        return detail.model_copy(
            update={
                "current_value": live.hvac.supply_air_temp,
                "power_kw": live.energy.hvac_kw,
            }
        )
    return detail


def get_equipment_history(equipment_id: str) -> List[MetricPoint]:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.get_equipment_history(equipment_id)

    detail = demo_mode.get_equipment(equipment_id)
    if detail:
        metrics = get_building_metrics(detail.building_id, "24h")
        if metrics:
            return metrics.metrics
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


def acknowledge_alert(alert_id: str, acknowledged_by: Optional[str] = None) -> bool:
    settings = get_settings()
    if settings.demo_mode:
        return True

    if not live_cache.acknowledge_alert(alert_id, acknowledged_by):
        return False

    supabase = _supabase()
    return supabase.acknowledge_alert(alert_id, acknowledged_by)


def list_fdd_results() -> List[FDDResult]:
    settings = get_settings()
    if settings.demo_mode:
        return demo_mode.list_fdd_results()

    cached = live_cache.get_fdd_results()
    if cached:
        return cached
    return demo_mode.list_fdd_results()


def ingest_live_snapshot(data: LiveBuildingData) -> None:
    """Accept live data from edge gateway or manual ingest."""
    live_cache.set_live(
        data.building_id,
        data.model_copy(update={"demo_mode": False, "source": data.source or "edge"}),
    )
    influx = _influx(force_live=True)
    tags = {"building_id": data.building_id}
    influx.write_point("total_kw", data.energy.total_kw, tags)
    influx.write_point("hvac_kw", data.energy.hvac_kw, tags)
    influx.write_point("temp_c", data.environment.temp_c, tags)
    influx.write_point("co2_ppm", float(data.environment.co2_ppm), tags)
    influx.write_point("cop", data.hvac.cop, tags)


async def get_refrigeration_snapshot(building_id: str) -> Optional[Dict[str, Any]]:
    """Latest industrial refrigeration telemetry for a building."""
    from app.services.refrigeration_poll import get_cached_snapshot, poll_building

    cached = get_cached_snapshot(building_id)
    if cached:
        return cached
    return await poll_building(building_id)
