"""Runtime Metasys object ID overrides (site survey → production mapping)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app.data.buildings_registry import BUILDING_REGISTRY, get_building_config

_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "metasys_objects.json"


def _load_overrides() -> Dict[str, Dict[str, str]]:
    if not _STORE_PATH.exists():
        return {}
    try:
        data = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_overrides(overrides: Dict[str, Dict[str, str]]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(overrides, indent=2), encoding="utf-8")


def get_metasys_objects(building_id: str) -> Dict[str, str]:
    """Merged registry defaults + runtime overrides."""
    cfg = get_building_config(building_id)
    base: Dict[str, str] = dict(cfg.get("metasys_objects", {})) if cfg else {}
    overrides = _load_overrides().get(building_id, {})
    base.update(overrides)
    return base


def set_metasys_objects(building_id: str, objects: Dict[str, str]) -> Dict[str, str]:
    if not get_building_config(building_id):
        raise ValueError(f"Unknown building: {building_id}")
    overrides = _load_overrides()
    overrides[building_id] = {k: str(v) for k, v in objects.items()}
    _save_overrides(overrides)
    return get_metasys_objects(building_id)


def list_all_mappings() -> Dict[str, Dict[str, str]]:
    return {cfg["id"]: get_metasys_objects(cfg["id"]) for cfg in BUILDING_REGISTRY}
