"""Per-building refrigeration connection source configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.data.buildings_registry import get_building_config

_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "refrigeration_connections.json"

DEFAULT_CONNECTION: Dict[str, Any] = {
    "source": "demo",
    "host": "",
    "port": 502,
    "poll_interval_seconds": 60,
}


def _load_all() -> Dict[str, Dict[str, Any]]:
    if not _STORE_PATH.exists():
        return {}
    try:
        data = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: Dict[str, Dict[str, Any]]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_refrigeration_connection(building_id: str) -> Dict[str, Any]:
    cfg = get_building_config(building_id)
    base = dict(DEFAULT_CONNECTION)
    if cfg and cfg.get("refrigeration_connection"):
        base.update(cfg["refrigeration_connection"])
    stored = _load_all().get(building_id, {})
    base.update(stored)
    return base


def set_refrigeration_connection(building_id: str, connection: Dict[str, Any]) -> Dict[str, Any]:
    if not get_building_config(building_id):
        raise ValueError(f"Unknown building: {building_id}")
    allowed = {"source", "host", "port", "poll_interval_seconds"}
    cleaned = {k: connection[k] for k in allowed if k in connection}
    all_data = _load_all()
    merged = {**get_refrigeration_connection(building_id), **cleaned}
    all_data[building_id] = merged
    _save_all(all_data)
    return merged
