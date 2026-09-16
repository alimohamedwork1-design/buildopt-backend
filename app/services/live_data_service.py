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
from app.models.user_context import UserContext
from app.services import demo_mode
from app.services.connection_store import connection_store
from app.services.data_policy import allows_simulated_telemetry
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


def list_buildings(user: Optional[UserContext] = None) -> List[BuildingSummary]:
    if allows_simulated_telemetry(user):
        return demo_mode.list_buildings()

    results = []
    for cfg in BUILDING_REGISTRY:
        cached = live_cache.get_live(cfg["id"])
        alerts = len([a for a in live_cache.get_alerts() if a.building_id == cfg["id"]])
        results.append(
            BuildingSummary(
                id=cfg["id"],
                name=cfg["name"],
                location=cfg["location"],
                floors=cfg["floors"],
                area_sqm=cfg["area_sqm"],
                status="online" if cached else "maintenance",
                # Aggregate verified savings are provided by the M&V workflow. Do not
                # infer a percentage from a live snapshot.
                energy_savings_pct=0.0,
                active_alerts=alerts,
                site_profile=get_site_profile(cfg["id"]),
            )
        )
    return results


def get_building(building_id: str, user: Optional[UserContext] = None) -> Optional[BuildingDetail]:
    if allows_simulated_telemetry(user):
        return demo_mode.get_building(building_id)

    cfg = get_building_config(building_id)
    if not cfg:
        return None
    summary = next((b for b in list_buildings(user=user) if b.id == building_id), None)
    if not summary:
        return None
    return BuildingDetail(
        **summary.model_dump(),
        bms_type=cfg["bms_type"],
        installed_capacity_kw=cfg["installed_capacity_kw"],
        last_updated=datetime.now(timezone.utc),
    )


async def get_live_data(building_id: str, user: Optional[UserContext] = None) -> Optional[LiveBuildingData]:
    if isinstance(user, UserContext) and user.is_live_account:
        row_conn = building_id in user.building_ids
        if not row_conn and not user.is_admin:
            return None

    cached = live_cache.get_live(building_id)
    if cached:
        if isinstance(user, UserContext) and user.is_live_account:
            return cached.model_copy(update={"demo_mode": False, "source": cached.source or "live"})
        return cached

    if isinstance(user, UserContext) and user.is_live_account:
        influx = _influx(force_live=True)
        from_influx = influx.get_latest_snapshot(building_id)
        if from_influx:
            live = from_influx.model_copy(update={"source": "influx", "demo_mode": False})
            live_cache.set_live(building_id, live)
            return live
        return None

    if allows_simulated_telemetry(user):
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
        influx.write_point("lighting_kw", live.energy.lighting_kw, tags)
        influx.write_point("other_kw", live.energy.other_kw, tags)
        influx.write_point("supply_air_temp", live.hvac.supply_air_temp, tags)
        influx.write_point("return_air_temp", live.hvac.return_air_temp, tags)
        influx.write_point("temp_c", live.environment.temp_c, tags)
        influx.write_point("humidity_pct", live.environment.humidity_pct, tags)
        influx.write_point("co2_ppm", float(live.environment.co2_ppm), tags)
        influx.write_point("pm25", live.environment.pm25, tags)
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

    # No plausible-number fallbacks in LIVE mode. The semantic mapper must supply
    # the minimum snapshot contract before the building can be considered live-ready.
    required = {
        "supply_air_temp",
        "return_air_temp",
        "hvac_power_kw",
        "total_kw",
        "lighting_kw",
        "other_kw",
        "temp_c",
        "humidity_pct",
        "co2_ppm",
        "pm25",
    }
    if not required.issubset(values):
        return None

    supply = values["supply_air_temp"]
    return_air = values["return_air_temp"]
    hvac_kw = values["hvac_power_kw"]
    total_kw = values["total_kw"]
    cop = values.get("cop")
    if cop is None:
        thermal_delta = max(return_air - supply, 0.0)
        if hvac_kw <= 0 or thermal_delta <= 0:
            return None
        # This derived COP is only a fallback when a mapped COP point is unavailable.
        # It is intentionally not clamped to a cosmetically plausible range.
        cop = thermal_delta / max(hvac_kw / 100.0, 0.1)

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
            cop=round(float(cop), 2),
        ),
        energy=EnergyData(
            total_kw=total_kw,
            hvac_kw=hvac_kw,
            lighting_kw=values["lighting_kw"],
            other_kw=values["other_kw"],
            tariff_rate=tariff,
            cost_per_hour=round(total_kw * tariff, 2),
        ),
        environment=EnvironmentData(
            temp_c=values["temp_c"],
            humidity_pct=values["humidity_pct"],
            co2_ppm=int(values["co2_ppm"]),
            pm25=values["pm25"],
        ),
        active_alerts=len([a for a in live_cache.get_alerts() if a.building_id == building_id]),
        demo_mode=False,
        source="metasys",
    )


def get_building_metrics(building_id: str, period: str = "24h", user: Optional[UserContext] = None) -> Optional[BuildingMetrics]:
    if isinstance(user, UserContext) and user.is_live_account:
        hours = {"1h": 1, "24h": 24, "7d": 168}.get(period, 24)
        influx = _influx(force_live=True)
        points = influx.query_metrics(building_id, hours=hours)
        if not points:
            return None
        metrics = [MetricPoint(timestamp=p["timestamp"], value=p["value"], metric=p["metric"]) for p in points]
        return BuildingMetrics(building_id=building_id, period=period, metrics=metrics)

    if allows_simulated_telemetry(user):
        return demo_mode.get_building_metrics(building_id, period)

    hours = {"1h": 1, "24h": 24, "7d": 168}.get(period, 24)
    influx = _influx()
    points = influx.query_metrics(building_id, hours=hours)
    if not points:
        return None

    metrics = [MetricPoint(timestamp=p["timestamp"], value=p["value"], metric=p["metric"]) for p in points]
    return BuildingMetrics(building_id=building_id, period=period, metrics=metrics)


def get_energy_consumption(
    building_id: str = "burj-khalifa-01",
    user: Optional[UserContext] = None,
) -> Optional[EnergyConsumption]:
    if allows_simulated_telemetry(user):
        return demo_mode.get_energy_consumption()

    live = live_cache.get_live(building_id)
    if not live:
        influx = _influx(force_live=True)
        live = influx.get_latest_snapshot(building_id)
    if not live:
        return None

    return EnergyConsumption(
        timestamp=live.timestamp,
        total_kw=live.energy.total_kw,
        hvac_kw=live.energy.hvac_kw,
        lighting_kw=live.energy.lighting_kw,
        other_kw=live.energy.other_kw,
        cost_aed_per_hour=round(live.energy.total_kw * live.energy.tariff_rate, 2),
        demo_mode=False,
    )


def get_energy_forecast(
    building_id: str,
    horizon_hours: int = 24,
    user: Optional[UserContext] = None,
) -> Optional[EnergyForecast]:
    if allows_simulated_telemetry(user):
        return demo_mode.get_energy_forecast(building_id, horizon_hours)

    # Lazy import avoids a module-import cycle: the forecaster reads history through
    # get_building_metrics().
    from app.ml.history_forecaster import HistoryForecaster

    result = HistoryForecaster().forecast(building_id, horizon_hours)
    if not result.get("available"):
        return None
    points = [
        EnergyForecastPoint(
            timestamp=datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00")),
            predicted_kw=float(row["predicted_kw"]),
            confidence=float(row["confidence"]),
        )
        for row in result.get("forecast", [])
    ]
    return EnergyForecast(
        building_id=building_id,
        horizon_hours=int(result["horizon_hours"]),
        forecast=points,
        demo_mode=False,
    )


def get_energy_savings(
    building_id: str = "burj-khalifa-01",
    user: Optional[UserContext] = None,
) -> Optional[EnergySavings]:
    if allows_simulated_telemetry(user):
        return demo_mode.get_energy_savings()

    # Use two real metered periods. Never invent a baseline by multiplying actual use.
    influx = _influx(force_live=True)
    history = [h for h in influx.query_hourly_kw(building_id, hours=1440) if h.get("metric") == "total_kw"]
    if not history:
        return None

    now = datetime.now(timezone.utc)
    reporting_start = now - timedelta(days=30)
    baseline_start = now - timedelta(days=60)
    baseline_values = [float(h["value"]) for h in history if baseline_start <= h["timestamp"] < reporting_start]
    reporting_values = [float(h["value"]) for h in history if h["timestamp"] >= reporting_start]

    # Require at least one week of hourly observations in each period.
    if len(baseline_values) < 168 or len(reporting_values) < 168:
        return None

    actual_kwh = sum(reporting_values)
    baseline_mean_kw = sum(baseline_values) / len(baseline_values)
    normalized_baseline_kwh = baseline_mean_kw * len(reporting_values)
    savings_kwh = normalized_baseline_kwh - actual_kwh
    savings_pct = (savings_kwh / normalized_baseline_kwh * 100.0) if normalized_baseline_kwh else 0.0

    live = live_cache.get_live(building_id) or influx.get_latest_snapshot(building_id)
    tariff_rate = live.energy.tariff_rate if live else 0.0
    return EnergySavings(
        baseline_kwh=round(normalized_baseline_kwh, 2),
        actual_kwh=round(actual_kwh, 2),
        savings_kwh=round(savings_kwh, 2),
        savings_pct=round(savings_pct, 2),
        cost_saved_aed=round(savings_kwh * tariff_rate, 2) if tariff_rate > 0 else 0.0,
        demo_mode=False,
    )


def get_dewa_tariff(
    building_id: str = "burj-khalifa-01",
    user: Optional[UserContext] = None,
) -> Optional[DewaTariffResponse]:
    if allows_simulated_telemetry(user):
        return demo_mode.get_dewa_tariff()

    cached = live_cache.get_dewa_tariff()
    if cached:
        return DewaTariffResponse(**cached)

    live = live_cache.get_live(building_id)
    if not live:
        influx = _influx(force_live=True)
        live = influx.get_latest_snapshot(building_id)
    if not live:
        return None

    peak_kwh = live.energy.total_kw * 12
    off_peak_kwh = live.energy.total_kw * 12
    # Until a separately metered kVA demand point is mapped, use the current kW as a
    # conservative proxy rather than a hard-coded site-wide demand value.
    demand_proxy = max(live.energy.total_kw, 0.0)
    tariff = calculate_dewa_tariff(peak_kwh, off_peak_kwh, demand_proxy)
    live_cache.set_dewa_tariff(tariff.model_dump(mode="json"))
    return tariff


def list_equipment(
    building_id: Optional[str] = None,
    user: Optional[UserContext] = None,
) -> List[EquipmentSummary]:
    if allows_simulated_telemetry(user):
        return demo_mode.list_equipment(building_id)

    bid = building_id or "burj-khalifa-01"
    live = live_cache.get_live(bid)
    if not live:
        influx = _influx(force_live=True)
        live = influx.get_latest_snapshot(bid)
    if not live:
        return []

    return [
        EquipmentSummary(
            id=f"{bid}-hvac-plant",
            name="HVAC Plant (derived live aggregate)",
            type="chiller",
            building_id=bid,
            status="running" if live.hvac.cop >= 3.2 else "fault",
            power_kw=live.energy.hvac_kw,
            efficiency=min(0.98, max(0.0, live.hvac.cop / 5.0)),
        )
    ]


def get_equipment(equipment_id: str, user: Optional[UserContext] = None) -> Optional[EquipmentDetail]:
    if allows_simulated_telemetry(user):
        return demo_mode.get_equipment(equipment_id)

    # A real equipment detail requires asset metadata (setpoint, maintenance date,
    # fault code). Do not hydrate those fields from the demo registry in LIVE mode.
    return None


def get_equipment_history(equipment_id: str, user: Optional[UserContext] = None) -> List[MetricPoint]:
    if allows_simulated_telemetry(user):
        return demo_mode.get_equipment_history(equipment_id)

    # History is exposed through mapped telemetry points/data-health until a durable
    # equipment/asset registry maps equipment_id -> building_id + point ids.
    return []


def list_alerts(user: Optional[UserContext] = None) -> List[Alert]:
    if allows_simulated_telemetry(user):
        return demo_mode.list_alerts()
    cached = live_cache.get_alerts()
    return cached or []


def list_alert_history(user: Optional[UserContext] = None) -> List[Alert]:
    alerts = list_alerts(user=user)
    return [a.model_copy(update={"acknowledged": True}) for a in alerts]


def acknowledge_alert(alert_id: str, acknowledged_by: Optional[str] = None) -> bool:
    settings = get_settings()
    if settings.demo_mode:
        return True

    if not live_cache.acknowledge_alert(alert_id, acknowledged_by):
        return False

    supabase = _supabase()
    return supabase.acknowledge_alert(alert_id, acknowledged_by)


def list_fdd_results(user: Optional[UserContext] = None, *, building_id: Optional[str] = None) -> List[FDDResult]:
    if allows_simulated_telemetry(user):
        return demo_mode.list_fdd_results()

    if building_id:
        from app.services.fdd_fault_store import get_fdd_fault_store
        faults = get_fdd_fault_store().list_active(building_id)
        if faults:
            results: List[FDDResult] = []
            for f in faults:
                results.append(FDDResult(
                    rule_id=f.get("rule_id", "FDD-000"),
                    category=f.get("equipment_type", "HVAC"),
                    equipment_id=f.get("equipment_id", building_id),
                    severity=f.get("severity", "warning"),
                    description=f.get("reason") or f.get("rule_id", "Fault"),
                    description_ar="تم اكتشاف عطل",
                    confidence=float(f.get("confidence", 0.85)),
                    detected_at=datetime.fromisoformat(f["detected_at"].replace("Z", "+00:00"))
                    if isinstance(f.get("detected_at"), str)
                    else datetime.now(timezone.utc),
                ))
            return results

    cached = live_cache.get_fdd_results()
    return cached or []


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
    influx.write_point("lighting_kw", data.energy.lighting_kw, tags)
    influx.write_point("other_kw", data.energy.other_kw, tags)
    influx.write_point("supply_air_temp", data.hvac.supply_air_temp, tags)
    influx.write_point("return_air_temp", data.hvac.return_air_temp, tags)
    influx.write_point("temp_c", data.environment.temp_c, tags)
    influx.write_point("humidity_pct", data.environment.humidity_pct, tags)
    influx.write_point("co2_ppm", float(data.environment.co2_ppm), tags)
    influx.write_point("pm25", data.environment.pm25, tags)
    influx.write_point("cop", data.hvac.cop, tags)


async def get_refrigeration_snapshot(building_id: str) -> Optional[Dict[str, Any]]:
    """Latest industrial refrigeration telemetry for a building."""
    from app.services.refrigeration_poll import get_cached_snapshot, poll_building

    cached = get_cached_snapshot(building_id)
    if cached:
        return cached
    return await poll_building(building_id)
