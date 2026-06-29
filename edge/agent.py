#!/usr/bin/env python3
"""BuildOpt edge gateway — polls BACnet/Modbus on-site and pushes to Railway API."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

API_URL = os.getenv("RAILWAY_API_URL", "https://buildopt-backend-production.up.railway.app").rstrip("/")
API_KEY = os.getenv("INGEST_API_KEY", "")
BUILDING_ID = os.getenv("BUILDING_ID", "burj-khalifa-01")
POLL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
MAX_RETRIES = int(os.getenv("INGEST_MAX_RETRIES", "5"))
QUEUE_DB = Path(os.getenv("EDGE_QUEUE_DB", "/data/edge_queue.db"))
ENABLE_BACNET = os.getenv("ENABLE_BACNET", "false").lower() == "true"

BACNET_IP = os.getenv("BACNET_IP", "192.168.1.100")
MODBUS_HOST = os.getenv("MODBUS_HOST", "192.168.1.101")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))


def init_queue() -> sqlite3.Connection:
    QUEUE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(QUEUE_DB)
    conn.execute(
        """
        create table if not exists pending_snapshots (
            id integer primary key autoincrement,
            payload text not null,
            created_at text not null,
            attempts integer default 0
        )
        """
    )
    conn.commit()
    return conn


def enqueue(conn: sqlite3.Connection, payload: dict) -> None:
    conn.execute(
        "insert into pending_snapshots (payload, created_at) values (?, ?)",
        (json.dumps(payload), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def dequeue_batch(conn: sqlite3.Connection, limit: int = 10) -> list[tuple[int, dict, int]]:
    rows = conn.execute(
        "select id, payload, attempts from pending_snapshots order by id asc limit ?",
        (limit,),
    ).fetchall()
    return [(row[0], json.loads(row[1]), row[2]) for row in rows]


def remove(conn: sqlite3.Connection, row_id: int) -> None:
    conn.execute("delete from pending_snapshots where id = ?", (row_id,))
    conn.commit()


def bump_attempts(conn: sqlite3.Connection, row_id: int) -> None:
    conn.execute("update pending_snapshots set attempts = attempts + 1 where id = ?", (row_id,))
    conn.commit()


def read_bacnet() -> dict:
    if not ENABLE_BACNET:
        return {}
    map_path = Path(__file__).resolve().parent / "bacnet_points.json"
    building_map: dict = {}
    if map_path.exists():
        try:
            all_maps = json.loads(map_path.read_text(encoding="utf-8"))
            building_map = all_maps.get(BUILDING_ID, {})
        except (json.JSONDecodeError, OSError):
            building_map = {}

    if not building_map:
        return {}

    readings: dict = {}
    try:
        import BAC0

        bacnet = BAC0.lite(ip=BACNET_IP)
        for key, point in building_map.items():
            device = point.get("device")
            obj = point.get("object")
            if not device or not obj:
                continue
            addr = f"{device} {obj}"
            try:
                val = bacnet.read(addr)
                if isinstance(val, (int, float)):
                    readings[key] = float(val)
                elif isinstance(val, (list, tuple)) and val:
                    readings[key] = float(val[0])
            except Exception:
                continue
        return readings
    except Exception:
        return {}


def read_local_sensors() -> dict:
    """Read BACnet/Modbus when available; otherwise return empty dict."""
    readings: dict = read_bacnet()

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


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    return headers


def push_snapshot(payload: dict) -> bool:
    backoff = 1.0
    for attempt in range(MAX_RETRIES):
        try:
            r = httpx.post(
                f"{API_URL}/api/v1/ingest/live",
                json=payload,
                headers=_headers(),
                timeout=15.0,
            )
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(min(backoff, 30))
        backoff *= 2
    return False


def send_heartbeat(protocol: str, data_points: int = 0) -> None:
    try:
        payload = {
            "building_id": BUILDING_ID,
            "protocol": protocol,
            "last_read_at": datetime.now(timezone.utc).isoformat(),
            "data_points": data_points,
        }
        httpx.post(
            f"{API_URL}/api/v1/ingest/heartbeat",
            json=payload,
            headers=_headers(),
            timeout=10.0,
        )
    except Exception:
        pass


def flush_queue(conn: sqlite3.Connection) -> None:
    for row_id, payload, attempts in dequeue_batch(conn):
        if push_snapshot(payload):
            remove(conn, row_id)
        else:
            bump_attempts(conn, row_id)
            if attempts + 1 >= MAX_RETRIES:
                remove(conn, row_id)


def main() -> None:
    print(f"BuildOpt edge agent → {API_URL} building={BUILDING_ID} bacnet={ENABLE_BACNET}")
    conn = init_queue()
    heartbeat_counter = 0

    while True:
        send_heartbeat("edge", data_points=0)
        flush_queue(conn)

        payload = read_local_sensors()
        if payload:
            ok = push_snapshot(payload)
            if not ok:
                enqueue(conn, payload)
            protocol = "bacnet" if ENABLE_BACNET else "modbus"
            send_heartbeat(protocol, data_points=len(payload.get("hvac", {})) + len(payload.get("energy", {})))
            print(
                f"{datetime.now(timezone.utc).isoformat()} push={'ok' if ok else 'queued'} "
                f"hvac_kw={payload['hvac']['power_kw']}"
            )
        else:
            print(f"{datetime.now(timezone.utc).isoformat()} no local sensor data (BACnet/Modbus unreachable)")

        heartbeat_counter += 1
        if heartbeat_counter % 10 == 0:
            pending = conn.execute("select count(*) from pending_snapshots").fetchone()[0]
            if pending:
                print(f"Queue depth: {pending} pending snapshots")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
