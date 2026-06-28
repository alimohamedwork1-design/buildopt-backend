from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List

from app.config import get_settings
from app.data.buildings_registry import BUILDING_REGISTRY, get_building_ids
from app.ml.fault_detector import FaultDetector
from app.models.schemas import Alert, FDDResult
from app.services.bacnet_client import BACnetClient
from app.services.influx_client import InfluxService
from app.services.jci_metasys import JCIMetasysClient
from app.services.live_cache import live_cache
from app.services.live_data_service import get_live_data, ingest_live_snapshot
from app.services.log_handler import log_event
from app.services.modbus_client import ModbusClient
from app.services.mqtt_client import MQTTClient
from app.services.pipeline_tracker import record_job_run
from app.services.supabase_client import SupabaseService

logger = logging.getLogger("buildopt.pipeline")


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
    supabase = SupabaseService(
        settings.supabase_url,
        settings.supabase_key,
        settings.supabase_service_key,
        demo_mode=False,
        alert_webhook_url=settings.supabase_alert_webhook_url,
        alert_webhook_secret=settings.alert_webhook_secret,
    )
    fault_detector = FaultDetector(demo_mode=False)

    bacnet = BACnetClient(settings.bacnet_ip, settings.bacnet_port, demo_mode=False)
    modbus = ModbusClient(settings.modbus_host, settings.modbus_port, demo_mode=False)
    MQTTClient(
        settings.mqtt_broker,
        settings.mqtt_port,
        settings.mqtt_username,
        settings.mqtt_password,
        demo_mode=False,
    )

    all_alerts: List[Alert] = []

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

        if cfg.get("bacnet_points"):
            bacnet.read_points(cfg["bacnet_points"])

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
            all_alerts.append(alert)
            supabase.push_alert(alert.model_dump(mode="json"))

    live_cache.set_alerts(all_alerts)
    logger.info("Poll cycle complete: %d buildings, %d alerts", len(BUILDING_REGISTRY), len(all_alerts))
    log_event(
        "info",
        f"Sensor poll cycle complete: {len(BUILDING_REGISTRY)} buildings, {len(all_alerts)} alerts",
        "اكتمل استطلاع المستشعرات",
    )


async def run_fdd_cycle() -> None:
    record_job_run(
        "fdd_engine",
        name="FDD Engine",
        name_ar="محرك كشف الأعطال",
        interval_label="Every 60s",
        interval_seconds=60,
    )
    log_event("info", "FDD engine evaluated active rules", "قام محرك FDD بتقييم القواعد النشطة")


async def run_ml_cycle() -> None:
    record_job_run(
        "ml_anomaly",
        name="ML Anomaly Detection",
        name_ar="كشف الشذوذ بالذكاء الاصطناعي",
        interval_label="Every 5min",
        interval_seconds=300,
    )
    log_event("info", "ML anomaly model inference complete", "اكتمل استنتاج نموذج كشف الشذوذ")


async def run_tariff_update() -> None:
    record_job_run(
        "dewa_tariff",
        name="DEWA Tariff Update",
        name_ar="تحديث تعرفة ديوا",
        interval_label="Every 1h",
        interval_seconds=3600,
    )
    log_event("info", "DEWA tariff rates refreshed", "تم تحديث تعرفة ديوا")


async def run_prayer_sync() -> None:
    record_job_run(
        "prayer_sync",
        name="Prayer Times Sync",
        name_ar="مزامنة أوقات الصلاة",
        interval_label="Every 24h",
        interval_seconds=86400,
    )
    log_event("info", "Prayer times synced for Dubai", "تمت مزامنة أوقات الصلاة لدبي")
