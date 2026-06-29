"""Load/save per-building Modbus and BACnet refrigeration point maps."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from app.data.buildings_registry import get_building_config

_MODBUS_PATH = Path(__file__).resolve().parent.parent / "data" / "refrigeration_modbus_map.json"
_BACNET_PATH = Path(__file__).resolve().parent.parent / "data" / "refrigeration_bacnet_map.json"


def _read_json(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: Path, data: Dict[str, Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_modbus_map(building_id: str) -> Dict[str, Any]:
    stored = _read_json(_MODBUS_PATH).get(building_id, {})
    cfg = get_building_config(building_id) or {}
    base = deepcopy(cfg.get("refrigeration_modbus_map", {}))
    base.update(stored)
    return base


def set_modbus_map(building_id: str, mapping: Dict[str, Any]) -> Dict[str, Any]:
    if not get_building_config(building_id):
        raise ValueError(f"Unknown building: {building_id}")
    all_data = _read_json(_MODBUS_PATH)
    all_data[building_id] = mapping
    _write_json(_MODBUS_PATH, all_data)
    return mapping


def get_bacnet_map(building_id: str) -> Dict[str, Any]:
    stored = _read_json(_BACNET_PATH).get(building_id, {})
    cfg = get_building_config(building_id) or {}
    base = deepcopy(cfg.get("refrigeration_bacnet_map", {}))
    base.update(stored)
    return base


def set_bacnet_map(building_id: str, mapping: Dict[str, Any]) -> Dict[str, Any]:
    if not get_building_config(building_id):
        raise ValueError(f"Unknown building: {building_id}")
    all_data = _read_json(_BACNET_PATH)
    all_data[building_id] = mapping
    _write_json(_BACNET_PATH, all_data)
    return mapping
