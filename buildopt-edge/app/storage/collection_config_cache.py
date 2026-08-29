"""Local last-known-good approved collection config — survives edge restart."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("buildopt.edge.config_cache")

_CACHE_FILENAME = "active_collection_config.json"


def _cache_path(queue_db_path: str) -> Path:
    base = Path(queue_db_path).parent
    base.mkdir(parents=True, exist_ok=True)
    return base / _CACHE_FILENAME


def _validate_mapping(mapping: Any) -> Optional[Dict[str, str]]:
    if not isinstance(mapping, dict) or not mapping:
        return None
    out: Dict[str, str] = {}
    for key, val in mapping.items():
        if not isinstance(key, str) or not key.strip():
            return None
        if not isinstance(val, str) or not val.strip():
            return None
        out[key] = val
    return out


def validate_cloud_config(body: Dict[str, Any]) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """Return (mapping, config_version) or (None, None) if malformed."""
    if not isinstance(body, dict):
        return None, None
    if body.get("status") == "DRAFT":
        return None, None
    mapping = _validate_mapping(body.get("mapping"))
    if not mapping:
        return None, None
    version = body.get("config_version")
    return mapping, str(version) if version else None


def load_cached_config(queue_db_path: str) -> Tuple[Dict[str, str], Optional[str]]:
    path = _cache_path(queue_db_path)
    if not path.exists():
        return {}, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Rejecting corrupted local config cache: %s", exc)
        return {}, None
    if not isinstance(data, dict) or data.get("source") != "cloud_approved":
        return {}, None
    mapping = _validate_mapping(data.get("mapping"))
    if not mapping:
        logger.warning("Rejecting invalid mapping in local config cache")
        return {}, None
    return mapping, data.get("config_version")


def save_cached_config(
    queue_db_path: str,
    *,
    mapping: Dict[str, str],
    config_version: Optional[str],
) -> None:
    validated = _validate_mapping(mapping)
    if not validated:
        return
    path = _cache_path(queue_db_path)
    payload = {
        "source": "cloud_approved",
        "config_version": config_version,
        "mapping": validated,
    }
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
