"""Typed API error codes for production data integrity."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.models.schemas import BilingualMessage


class ErrorCode(str, Enum):
    DEMO_DATA_FORBIDDEN = "DEMO_DATA_FORBIDDEN"
    INTEGRATION_NOT_CONFIGURED = "INTEGRATION_NOT_CONFIGURED"
    INTEGRATION_UNAVAILABLE = "INTEGRATION_UNAVAILABLE"
    NO_TELEMETRY = "NO_TELEMETRY"
    STALE_TELEMETRY = "STALE_TELEMETRY"
    POINT_NOT_MAPPED = "POINT_NOT_MAPPED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TENANT_ACCESS_DENIED = "TENANT_ACCESS_DENIED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    COMMAND_NOT_ALLOWED = "COMMAND_NOT_ALLOWED"
    NO_BUILDING_CONNECTED = "NO_BUILDING_CONNECTED"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"


def api_error(
    code: ErrorCode,
    message_en: str,
    message_ar: str,
    *,
    status_code: int = 400,
    extra: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    detail: Dict[str, Any] = {
        "code": code.value,
        "message": BilingualMessage(en=message_en, ar=message_ar).model_dump(),
    }
    if extra:
        detail.update(extra)
    return HTTPException(status_code=status_code, detail=detail)
