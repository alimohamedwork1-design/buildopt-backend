"""Registered buildings and BMS point mappings for production mode."""

from typing import Any, Dict, List

BUILDING_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "burj-khalifa-01",
        "name": "Burj Khalifa Tower A",
        "location": "Downtown Dubai, UAE",
        "floors": 163,
        "area_sqm": 309473.0,
        "bms_type": "Johnson Controls Metasys",
        "installed_capacity_kw": 5200.0,
        "metasys_objects": {
            "supply_air_temp": "obj-1001",
            "return_air_temp": "obj-1002",
            "hvac_power_kw": "obj-1010",
            "total_kw": "obj-1020",
        },
        "refrigeration_objects": {},
        "refrigeration_connection": {"source": "modbus", "host": "192.168.1.101", "port": 502, "poll_interval_seconds": 60},
        "bacnet_points": [],
        "modbus_registers": [],
    },
    {
        "id": "dubai-mall-01",
        "name": "Dubai Mall Central Plant",
        "location": "Downtown Dubai, UAE",
        "floors": 4,
        "area_sqm": 502000.0,
        "bms_type": "Johnson Controls OpenBlue",
        "installed_capacity_kw": 8400.0,
        "metasys_objects": {},
        "bacnet_points": [],
        "modbus_registers": [],
    },
    {
        "id": "difc-gate-01",
        "name": "DIFC Gate Building",
        "location": "DIFC, Dubai, UAE",
        "floors": 15,
        "area_sqm": 45000.0,
        "bms_type": "Honeywell Niagara",
        "installed_capacity_kw": 1200.0,
        "metasys_objects": {},
        "bacnet_points": [],
        "modbus_registers": [],
    },
]


def get_building_ids() -> List[str]:
    return [b["id"] for b in BUILDING_REGISTRY]


def get_building_config(building_id: str) -> Dict[str, Any] | None:
    return next((b for b in BUILDING_REGISTRY if b["id"] == building_id), None)
