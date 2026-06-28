from fastapi import APIRouter

from app.config import get_settings
from app.services.bacnet_client import BACnetClient
from app.services.modbus_client import ModbusClient
from app.services.mqtt_client import MQTTClient

router = APIRouter(prefix="/protocols", tags=["protocols"])


@router.get("/status")
async def protocol_status() -> dict:
    settings = get_settings()
    bacnet = BACnetClient(settings.bacnet_ip, settings.bacnet_port, settings.demo_mode)
    modbus = ModbusClient(settings.modbus_host, settings.modbus_port, settings.demo_mode)
    mqtt = MQTTClient(
        settings.mqtt_broker,
        settings.mqtt_port,
        settings.mqtt_username,
        settings.mqtt_password,
        settings.demo_mode,
    )
    return {
        "bacnet": bacnet.status(),
        "modbus": modbus.status(),
        "mqtt": mqtt.status(),
        "demo_mode": settings.demo_mode,
    }
