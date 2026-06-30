"""Per-building site profile (commercial HVAC vs industrial cooling scope)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from app.data.buildings_registry import get_building_config

SiteProfile = Literal[
    "building_only",
    "building_with_industrial_cooling",
    "industrial_cooling_only",
]

VALID_PROFILES: frozenset[str] = frozenset(
    {"building_only", "building_with_industrial_cooling", "industrial_cooling_only"}
)

DEFAULT_PROFILE: SiteProfile = "building_only"

_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "site_profiles.json"


def _load_all() -> dict[str, str]:
    if not _STORE_PATH.exists():
        return {}
    try:
        data = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(v, str) and v in VALID_PROFILES}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict[str, str]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_site_profile(building_id: str) -> SiteProfile:
    cfg = get_building_config(building_id)
    if not cfg:
        raise ValueError(f"Unknown building: {building_id}")
    stored = _load_all().get(building_id)
    if stored:
        return stored  # type: ignore[return-value]
    registry_val = cfg.get("site_profile")
    if registry_val in VALID_PROFILES:
        return registry_val  # type: ignore[return-value]
    return DEFAULT_PROFILE


def set_site_profile(building_id: str, site_profile: str) -> SiteProfile:
    if site_profile not in VALID_PROFILES:
        raise ValueError(f"Invalid site_profile: {site_profile}")
    if not get_building_config(building_id):
        raise ValueError(f"Unknown building: {building_id}")
    all_data = _load_all()
    all_data[building_id] = site_profile
    _save_all(all_data)
    return site_profile  # type: ignore[return-value]


def shows_hvac_connection(profile: SiteProfile) -> bool:
    return profile in ("building_only", "building_with_industrial_cooling")


def shows_refrigeration_connection(profile: SiteProfile) -> bool:
    return profile in ("building_with_industrial_cooling", "industrial_cooling_only")
