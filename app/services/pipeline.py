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
from app.services.modbus_client import ModbusClient
from app.services.mqtt_client import MQTTClient
from app.services.supabase_client import SupabaseService

logger = logging.getLogger("buildopt.pipeline")


async def run_poll_cycle() -> None:
    settings = get_settings()
    if settings.demo_mode:
        for building_id in get_building_ids():
            data = await get_live_data(building_id)
            if data:
                live_cache.set_live(building_id, data)
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
