from app.services.bacnet_client import BACnetClient
from app.services.modbus_client import ModbusClient
from app.services.mqtt_client import MQTTClient


def test_bacnet_demo_status():
    client = BACnetClient("192.168.1.100", 47808, demo_mode=True)
    assert client.status() == "simulated"


def test_modbus_demo_status():
    client = ModbusClient("192.168.1.101", 502, demo_mode=True)
    assert client.status() == "simulated"


def test_mqtt_demo_status():
    client = MQTTClient("localhost", 1883, "buildopt", "pass", demo_mode=True)
    assert client.status() == "simulated"
    assert client.publish("buildopt/test", "ok") is True
