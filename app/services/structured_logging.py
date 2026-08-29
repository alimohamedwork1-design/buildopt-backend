"""Structured operational logging — no secrets."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("buildopt.ops")

_SENSITIVE_KEYS = frozenset({
    "password", "token", "api_key", "authorization", "secret", "service_key",
    "supabase_key", "influx_token", "gateway_token",
})


def _scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: "***" if k.lower() in _SENSITIVE_KEYS else _scrub(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_scrub(x) for x in obj[:20]]
    return obj


def log_event(
    event: str,
    *,
    level: str = "info",
    request_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    building_id: Optional[str] = None,
    gateway_id: Optional[str] = None,
    error: Optional[str] = None,
    **fields: Any,
) -> None:
    payload: Dict[str, Any] = {
        "event": event,
        "request_id": request_id,
        "tenant_id": tenant_id,
        "building_id": building_id,
        "gateway_id": gateway_id,
        **_scrub(fields),
    }
    if error:
        payload["error"] = str(error)[:500]
    msg = json.dumps({k: v for k, v in payload.items() if v is not None}, default=str)
    getattr(logger, level, logger.info)(msg)
