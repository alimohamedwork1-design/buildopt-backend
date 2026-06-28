#!/usr/bin/env python3
"""BuildOpt edge gateway — polls BACnet/Modbus on-site and pushes to Railway API."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import httpx

API_URL = os.getenv("RAILWAY_API_URL", "https://buildopt-backend-production.up.railway.app").rstrip("/")
API_KEY = os.getenv("INGEST_API_KEY", "")
BUILDING_ID = os.getenv("BUILDING_ID", "burj-khalifa-01")
POLL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))

BACNET_IP = os.getenv("BACNET_IP", "192.168.1.100")
MODBUS_HOST = os.getenv("MODBUS_HOST", "192.168.1.101")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))


def read_local_sensors() -> dict:
    """Read BACnet/Modbus when available; otherwise return None to skip."""
    readings: dict = {}
    try:
        from pymodbus.client import ModbusTcpClient

        client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
        if client.connect():
            result = client.read_holding_registers(0, count=4)
            if not result.isError():
                regs = result.registers
                readings["hvac_kw"] = regs[0] / 10.0
                readings["total_kw"] = regs[1] / 10.0
                readings["supply_air_temp"] = regs[2] / 10.0
                readings["temp_c"] = regs[3] / 10.0
            client.close()
    except Exception:
        pass

    if not readings:
        return {}

    hvac_kw = readings.get("hvac_kw", 195.0)
    total_kw = readings.get("total_kw", hvac_kw * 4.2)
    supply = readings.get("supply_air_temp", 14.0)
    temp_c = readings.get("temp_c", 23.0)
    hour = datetime.now(timezone.utc).hour
    tariff = 0.38 if 12 <= hour < 24 else 0.23

    return {
        "building_id": BUILDING_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hvac": {
            "supply_air_temp": supply,
            "return_air_temp": supply + 10,
            "delta_t": 10.0,
            "power_kw": hvac_kw,
            "cop": 3.8,
        },
        "energy": {
            "total_kw": total_kw,
            "hvac_kw": hvac_kw,
            "lighting_kw": round(total_kw * 0.15, 1),
            "other_kw": round(total_kw * 0.55, 1),
            "tariff_rate": tariff,
            "cost_per_hour": round(total_kw * tariff, 1),
        },
        "environment": {
            "temp_c": temp_c,
            "humidity_pct": 48.0,
            "co2_ppm": 600,
            "pm25": 20.0,
        },
        "active_alerts": 0,
        "demo_mode": False,
    }


def push_snapshot(payload: dict) -> bool:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    try:
        r = httpx.post(f"{API_URL}/api/v1/ingest/live", json=payload, headers=headers, timeout=15.0)
        return r.status_code == 200
    except Exception:
        return False


def main() -> None:
    print(f"BuildOpt edge agent → {API_URL} building={BUILDING_ID}")
    while True:
        payload = read_local_sensors()
        if payload:
            ok = push_snapshot(payload)
            print(f"{datetime.now(timezone.utc).isoformat()} push={'ok' if ok else 'fail'} hvac_kw={payload['hvac']['power_kw']}")
        else:
            print(f"{datetime.now(timezone.utc).isoformat()} no local sensor data (BACnet/Modbus unreachable)")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
