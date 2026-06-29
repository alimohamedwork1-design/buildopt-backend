from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List

from app.config import get_settings
from app.data.buildings_registry import BUILDING_REGISTRY, get_building_ids
from app.ml.anomaly_detector import AnomalyDetector
from app.ml.fault_detector import FaultDetector
from app.models.schemas import Alert, FDDResult
from app.services.connection_store import connection_store
from app.services.influx_client import InfluxService
from app.services.jci_metasys import JCIMetasysClient
from app.services.live_cache import live_cache
from app.services.live_data_service import get_live_data, poll_metasys_buildings
from app.services.log_handler import log_event
from app.services.pipeline_tracker import record_job_run
from app.services.supabase_client import SupabaseService
from app.utils.dewa_tariff import calculate_dewa_tariff
from app.utils.gcc_features import get_prayer_times

logger = logging.getLogger("buildopt.pipeline")


def _supabase() -> SupabaseService:
    settings = get_settings()
    return SupabaseService(
        settings.supabase_url,
        settings.supabase_key,
        settings.supabase_service_key,
        demo_mode=settings.demo_mode,
        alert_webhook_url=settings.supabase_alert_webhook_url,
        alert_webhook_secret=settings.alert_webhook_secret,
    )


def _fault_to_fdd(fault: dict, building_id: str) -> FDDResult:
    return FDDResult(
        rule_id=fault.get("rule_id", "FDD-000"),
        category=fault.get("category", "HVAC"),
        equipment_id=fault.get("equipment_id", building_id),
        severity=fault.get("severity", "warning"),
        description=fault.get("description", "Fault detected"),
        description_ar=fault.get("description_ar", "تم اكتشاف عطل"),
        confidence=float(fault.get("confidence", 0.85)),
        detected_at=datetime.fromisoformat(fault["detected_at"].replace("Z", "+00:00"))
        if isinstance(fault.get("detected_at"), str)
        else datetime.now(timezone.utc),
    )


async def run_poll_cycle() -> None:
    settings = get_settings()
    record_job_run(
        "sensor_poll",
        name="Sensor Poll",
        name_ar="استطلاع المستشعرات",
        interval_label="Every 30s",
        interval_seconds=settings.poll_interval_seconds,
    )
    if settings.demo_mode:
        for building_id in get_building_ids():
            data = await get_live_data(building_id)
            if data:
                live_cache.set_live(building_id, data)
        log_event("info", f"Sensor poll cycle complete: {len(get_building_ids())} buildings", "اكتمل استطلاع المستشعرات")
        return

    influx = InfluxService(
        settings.influx_url,
        settings.influx_token,
        settings.influx_org,
        settings.influx_bucket,
        demo_mode=False,
    )
    supabase = _supabase()
    fault_detector = FaultDetector(demo_mode=False)

    metasys_polled = await poll_metasys_buildings()
    all_alerts: List[Alert] = list(live_cache.get_alerts())

    for cfg in BUILDING_REGISTRY:
        building_id = cfg["id"]
        live = await get_live_data(building_id)
        if not live:
            continue

        live_cache.set_live(building_id, live)
        tags = {"building_id": building_id}
        influx.write_point("total_kw", live.energy.total_kw, tags)
        influx.write_point("hvac_kw", live.energy.hvac_kw, tags)
        influx.write_point("supply_air_temp", live.hvac.supply_air_temp, tags)
        influx.write_point("temp_c", live.environment.temp_c, tags)
        influx.write_point("co2_ppm", float(live.environment.co2_ppm), tags)
        influx.write_point("cop", live.hvac.cop, tags)

        readings = {
            "cop": live.hvac.cop,
            "supply_air_temp_deviation": abs(live.hvac.return_air_temp - live.hvac.supply_air_temp - 10),
            "baseline_deviation_pct": 0,
            "filter_pressure_pa": 100,
        }
        faults = fault_detector.evaluate(readings)
        for fault in faults:
            alert = Alert(
                id=f"alert-{uuid.uuid4().hex[:8]}",
                building_id=building_id,
                equipment_id=fault.get("equipment_id"),
                severity=fault.get("severity", "warning"),
                category=fault.get("category", "FDD"),
                title=fault.get("description", "Fault detected")[:80],
                message=fault.get("description", ""),
                message_ar=fault.get("description_ar", "تم اكتشاف عطل"),
                timestamp=datetime.now(timezone.utc),
                acknowledged=False,
            )
            if not any(a.title == alert.title and a.building_id == building_id for a in all_alerts):
                all_alerts.append(alert)
                supabase.push_alert(alert.model_dump(mode="json"))

    live_cache.set_alerts(all_alerts)
    logger.info(
        "Poll cycle complete: %d buildings, %d metasys, %d alerts",
        len(BUILDING_REGISTRY),
        metasys_polled,
        len(all_alerts),
    )
    log_event(
        "info",
        f"Sensor poll complete: {len(BUILDING_REGISTRY)} buildings, Metasys={metasys_polled}, alerts={len(all_alerts)}",
        "اكتمل استطلاع المستشعرات",
    )


async def run_fdd_cycle() -> None:
    settings = get_settings()
    record_job_run(
        "fdd_engine",
        name="FDD Engine",
        name_ar="محرك كشف الأعطال",
        interval_label="Every 60s",
        interval_seconds=60,
    )

    if settings.demo_mode:
        log_event("info", "FDD engine evaluated active rules (demo)", "قام محرك FDD بتقييم القواعد النشطة")
        return

    fault_detector = FaultDetector(demo_mode=False)
    supabase = _supabase()
    results: List[FDDResult] = []
    new_alerts: List[Alert] = list(live_cache.get_alerts())

    for cfg in BUILDING_REGISTRY:
        building_id = cfg["id"]
        live = live_cache.get_live(building_id) or await get_live_data(building_id)
        if not live:
            continue

        readings = {
            "cop": live.hvac.cop,
            "supply_air_temp_deviation": abs(live.hvac.return_air_temp - live.hvac.supply_air_temp - 10),
            "baseline_deviation_pct": max(0, (live.energy.total_kw - 800) / 800 * 100),
            "filter_pressure_pa": 180 if live.hvac.cop < 3.5 else 90,
            "power_factor": 0.88,
        }
        for fault in fault_detector.evaluate(readings):
            fdd = _fault_to_fdd(fault, building_id)
            if not any(r.rule_id == fdd.rule_id and r.equipment_id == fdd.equipment_id for r in results):
                results.append(fdd)
                alert = Alert(
                    id=f"alert-{uuid.uuid4().hex[:8]}",
                    building_id=building_id,
                    equipment_id=fdd.equipment_id,
                    severity=fdd.severity,
                    category=fdd.category,
                    title=fdd.description[:80],
                    message=fdd.description,
                    message_ar=fdd.description_ar,
                    timestamp=fdd.detected_at,
                    acknowledged=False,
                )
                if not any(a.title == alert.title and a.building_id == building_id for a in new_alerts):
                    new_alerts.append(alert)
                    supabase.push_alert(alert.model_dump(mode="json"))

    live_cache.set_fdd_results(results)
    live_cache.set_alerts(new_alerts)
    log_event(
        "info",
        f"FDD engine: {len(results)} faults across {len(BUILDING_REGISTRY)} buildings",
        f"محرك FDD: {len(results)} أعطال",
    )


async def run_ml_cycle() -> None:
    settings = get_settings()
    record_job_run(
        "ml_anomaly",
        name="ML Anomaly Detection",
        name_ar="كشف الشذوذ بالذكاء الاصطناعي",
        interval_label="Every 5min",
        interval_seconds=300,
    )

    if settings.demo_mode:
        log_event("info", "ML anomaly model inference complete (demo)", "اكتمل استنتاج نموذج كشف الشذوذ")
        return

    influx = InfluxService(
        settings.influx_url,
        settings.influx_token,
        settings.influx_org,
        settings.influx_bucket,
        demo_mode=False,
    )
    detector = AnomalyDetector(demo_mode=False)
    anomaly_count = 0

    for cfg in BUILDING_REGISTRY:
        history = influx.query_hourly_kw(cfg["id"], hours=6)
        metrics = [
            {
                "total_kw": h["value"],
                "hvac_kw": h["value"] * 0.4,
                "temp_c": 23.0,
            }
            for h in history
            if h.get("metric") == "total_kw"
        ]
        anomalies = detector.detect(metrics)
        anomaly_count += sum(1 for a in anomalies if a.get("is_anomaly"))

    log_event(
        "info",
        f"ML anomaly inference complete: {anomaly_count} anomalies flagged",
        f"اكتمل كشف الشذوذ: {anomaly_count} حالات",
    )


async def run_tariff_update() -> None:
    settings = get_settings()
    record_job_run(
        "dewa_tariff",
        name="DEWA Tariff Update",
        name_ar="تحديث تعرفة ديوا",
        interval_label="Every 1h",
        interval_seconds=3600,
    )

    live = live_cache.get_live("burj-khalifa-01")
    peak_kwh = (live.energy.total_kw * 12) if live else 52000.0
    off_peak_kwh = (live.energy.total_kw * 12) if live else 34000.0
    tariff = calculate_dewa_tariff(peak_kwh, off_peak_kwh, 950.0)
    live_cache.set_dewa_tariff(tariff.model_dump(mode="json"))
    log_event(
        "info",
        f"DEWA tariff refreshed: AED {tariff.total_cost_aed:,.0f} projected",
        "تم تحديث تعرفة ديوا",
    )


async def run_metasys_keepalive() -> None:
    """Refresh Metasys JWT before 14-minute expiry."""
    settings = get_settings()
    if settings.demo_mode or not connection_store.has_saved_metasys():
        return
    record_job_run(
        "metasys_keepalive",
        name="Metasys Token Refresh",
        name_ar="تجديد رمز Metasys",
        interval_label="Every 10min",
        interval_seconds=600,
    )
    creds = connection_store.get_metasys()
    client = JCIMetasysClient(
        creds.host,
        creds.username,
        creds.password,
        creds.version,
        demo_mode=False,
    )
    probe = await client.health_probe()
    if probe.get("status") == "connected":
        log_event("info", "Metasys token refreshed", "تم تجديد رمز Metasys")
    else:
        log_event("warning", "Metasys keepalive failed", "فشل تجديد Metasys")


async def run_prayer_sync() -> None:
    record_job_run(
        "prayer_sync",
        name="Prayer Times Sync",
        name_ar="مزامنة أوقات الصلاة",
        interval_label="Every 24h",
        interval_seconds=86400,
    )
    times = await get_prayer_times()
    live_cache.set_prayer_times(times.model_dump(mode="json"))
    log_event("info", "Prayer times synced for Dubai", "تمت مزامنة أوقات الصلاة لدبي")
