"""Poll industrial refrigeration points via Modbus TCP or BACnet."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.config import get_settings
from app.data.buildings_registry import BUILDING_REGISTRY
from app.services.bacnet_client import BACnetClient
from app.services.connection_store import connection_store
from app.services.jci_metasys import JCIMetasysClient
from app.services.modbus_client import ModbusClient
from app.services.refrigeration_connection_store import get_refrigeration_connection
from app.services.refrigeration_map_store import get_bacnet_map, get_modbus_map
from app.services.refrigeration_object_store import get_refrigeration_objects
from app.services.influx_client import InfluxService

# In-memory latest snapshots per building
_refrig_cache: Dict[str, Dict[str, Any]] = {}


def get_cached_snapshot(building_id: str) -> Optional[Dict[str, Any]]:
    return _refrig_cache.get(building_id)


def set_cached_snapshot(building_id: str, snapshot: Dict[str, Any]) -> None:
    _refrig_cache[building_id] = snapshot


async def _fetch_from_metasys(building_id: str) -> Dict[str, float]:
    objects = get_refrigeration_objects(building_id)
    if not objects or not connection_store.has_saved_metasys():
        return {}

    creds = connection_store.get_metasys()
    client = JCIMetasysClient(
        creds.host,
        creds.username,
        creds.password,
        creds.version,
        demo_mode=False,
    )
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
    return values


def _fetch_from_modbus(building_id: str) -> Dict[str, float]:
    settings = get_settings()
    conn = get_refrigeration_connection(building_id)
    host = conn.get("host") or settings.modbus_host
    port = int(conn.get("port") or settings.modbus_port)
    mapping = get_modbus_map(building_id)
    if not mapping:
        return {}

    client = ModbusClient(host, port, demo_mode=settings.demo_mode)
    values: Dict[str, float] = {}
    for key, spec in mapping.items():
        if not isinstance(spec, dict):
            continue
        address = int(spec.get("address", 0))
        scale = float(spec.get("scale", 1.0))
        regs = client.read_registers(address, 1)
        if regs:
            values[key] = round(regs[0] * scale, 3)
    return values


def _fetch_from_bacnet(building_id: str) -> Dict[str, float]:
    settings = get_settings()
    conn = get_refrigeration_connection(building_id)
    mapping = get_bacnet_map(building_id)
    if not mapping:
        return {}

    ip = conn.get("host") or settings.bacnet_ip
    port = int(conn.get("port") or settings.bacnet_port)
    client = BACnetClient(ip, port, settings.demo_mode)
    values: Dict[str, float] = {}
    points = [spec.get("object_id") for spec in mapping.values() if isinstance(spec, dict) and spec.get("object_id")]
    if not points:
        return {}
    readings = client.read_points(points)
    for key, spec in mapping.items():
        if not isinstance(spec, dict):
            continue
        oid = spec.get("object_id")
        if oid and oid in readings:
            try:
                values[key] = float(readings[oid])
            except (TypeError, ValueError):
                pass
    return values


def _build_snapshot(building_id: str, values: Dict[str, float], source: str) -> Dict[str, Any]:
    cop = values.get("refrig_cop", 3.42)
    kw = values.get("compressor_kw", 842.0)
    return {
        "building_id": building_id,
        "connection_source": source,
        "total_load_kw": kw,
        "system_cop": cop,
        "suction_pressure_bar": values.get("suction_pressure_bar"),
        "discharge_pressure_bar": values.get("discharge_pressure_bar"),
        "evap_temp_c": values.get("evap_temp_c"),
        "superheat_k": values.get("superheat_k"),
        "subcooling_k": values.get("subcooling_k"),
        "nh3_ppm": values.get("nh3_ppm", 0),
        "defrost_active": bool(values.get("defrost_active")),
        "readings": values,
    }


def _write_influx(building_id: str, values: Dict[str, float]) -> None:
    settings = get_settings()
    if settings.demo_mode:
        return
    influx = InfluxService(
        settings.influx_url,
        settings.influx_token,
        settings.influx_org,
        settings.influx_bucket,
        demo_mode=False,
    )
    tags = {"building_id": building_id, "domain": "refrigeration"}
    for key, val in values.items():
        if isinstance(val, (int, float)):
            influx.write_point(f"refrig_{key}", float(val), tags)


async def poll_building(building_id: str) -> Optional[Dict[str, Any]]:
    conn = get_refrigeration_connection(building_id)
    source = str(conn.get("source", "demo")).lower()
    settings = get_settings()

    if source == "demo" or settings.demo_mode:
        snapshot = _demo_snapshot(building_id, source if source != "demo" else "demo")
        set_cached_snapshot(building_id, snapshot)
        return snapshot

    values: Dict[str, float] = {}
    if source == "bms":
        values = await _fetch_from_metasys(building_id)
    elif source == "modbus":
        values = _fetch_from_modbus(building_id)
    elif source == "bacnet":
        values = _fetch_from_bacnet(building_id)

    if not values:
        return None

    snapshot = _build_snapshot(building_id, values, source)
    set_cached_snapshot(building_id, snapshot)
    _write_influx(building_id, values)
    return snapshot


async def poll_all_buildings(*, include_demo: bool = False) -> int:
    polled = 0
    for cfg in BUILDING_REGISTRY:
        conn = get_refrigeration_connection(cfg["id"])
        source = str(conn.get("source", "demo")).lower()
        if source == "demo" and not include_demo:
            continue
        result = await poll_building(cfg["id"])
        if result:
            polled += 1
    return polled


def _demo_snapshot(building_id: str, source: str) -> Dict[str, Any]:
    return _build_snapshot(
        building_id,
        {
            "compressor_kw": 842.0,
            "refrig_cop": 3.42,
            "suction_pressure_bar": 2.1,
            "discharge_pressure_bar": 14.8,
            "evap_temp_c": -17.4,
            "superheat_k": 8.2,
            "subcooling_k": 4.5,
            "nh3_ppm": 0,
            "defrost_active": 0,
        },
        source,
    )
