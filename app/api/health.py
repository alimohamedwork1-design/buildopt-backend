from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import get_settings
from app.models.schemas import HealthResponse, ProtocolStatus
from app.services.bacnet_client import BACnetClient
from app.services.modbus_client import ModbusClient
from app.services.mqtt_client import MQTTClient
from app.services.jci_metasys import JCIMetasysClient

router = APIRouter(prefix="/health", tags=["health"])

API_VERSION = "1.0.0"


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version=API_VERSION,
        demo_mode=settings.demo_mode,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/connections")
async def connection_health() -> dict:
    settings = get_settings()
    from app.database import get_influx_service, get_supabase_service

    influx = get_influx_service()
    supabase = get_supabase_service()
    jci = JCIMetasysClient(
        settings.jci_metasys_host,
        settings.jci_metasys_username,
        settings.jci_metasys_password,
        settings.jci_metasys_version,
        settings.demo_mode,
    )

    return {
        "demo_mode": settings.demo_mode,
        "influxdb": influx.status(),
        "supabase": supabase.status(),
        "jci_metasys": jci.status(),
        "alert_webhook": bool(settings.supabase_alert_webhook_url),
        "ingest_api": bool(settings.ingest_api_key),
        "frontend": "https://build-opt.site",
        "api_url": "https://buildopt-backend-production.up.railway.app",
    }


@router.get("/protocols", response_model=ProtocolStatus)
async def protocol_health() -> ProtocolStatus:
    settings = get_settings()
    if settings.demo_mode:
        return ProtocolStatus(
            bacnet="simulated",
            modbus="simulated",
            mqtt="simulated",
            jci_metasys="simulated",
        )

    bacnet = BACnetClient(settings.bacnet_ip, settings.bacnet_port, demo_mode=False)
    modbus = ModbusClient(settings.modbus_host, settings.modbus_port, demo_mode=False)
    mqtt = MQTTClient(
        settings.mqtt_broker,
        settings.mqtt_port,
        settings.mqtt_username,
        settings.mqtt_password,
        demo_mode=False,
    )
    jci = JCIMetasysClient(
        settings.jci_metasys_host,
        settings.jci_metasys_username,
        settings.jci_metasys_password,
        settings.jci_metasys_version,
        demo_mode=False,
    )

    return ProtocolStatus(
        bacnet=bacnet.status(),
        modbus=modbus.status(),
        mqtt=mqtt.status(),
        jci_metasys=jci.status(),
    )
