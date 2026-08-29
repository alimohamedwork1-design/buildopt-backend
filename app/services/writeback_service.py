"""Writeback foundation — disabled by default, explicit gates."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.write_policy import DEFAULT_CONTROL_MATURITY, DEFAULT_WRITE_MODE, ControlMaturity, WriteMode, validate_write_request
from app.models.user_context import UserContext

WRITEBACK_ENABLED = os.getenv("WRITEBACK_ENABLED", "false").lower() == "true"
ALLOWED_POINTS: Dict[str, List[str]] = {}
AUDIT_LOG: List[Dict[str, Any]] = []


def writeback_status(site_id: Optional[str] = None) -> Dict[str, Any]:
    allowed = ALLOWED_POINTS.get(site_id or "", []) if site_id else []
    return {
        "writeback_enabled": WRITEBACK_ENABLED,
        "write_mode": DEFAULT_WRITE_MODE.value,
        "control_maturity": DEFAULT_CONTROL_MATURITY.value,
        "control_maturity_label": "L0 Monitoring / L1 Recommendation",
        "autonomous_control": False,
        "site_id": site_id,
        "site_enablement": "disabled" if not WRITEBACK_ENABLED else "gated",
        "allowlist_state": "empty" if not allowed else f"{len(allowed)} points",
        "allowed_points_count": len(allowed),
        "command_limits": {
            "max_step_pct": 5,
            "human_approval_required": True,
            "min_interval_seconds": 300,
        },
        "human_approval_required": True,
        "audit_ready": True,
        "audit_entries": len(AUDIT_LOG),
        "message": "READ_ONLY — production writeback disabled by default; no BMS commands sent",
    }


def request_writeback(
    user: UserContext,
    *,
    site_id: str,
    point_id: str,
    current_value: float,
    requested_value: float,
    min_value: float,
    max_value: float,
    max_step: float,
    approval_token: Optional[str] = None,
) -> Dict[str, Any]:
    if not WRITEBACK_ENABLED:
        validate_write_request(user, mode=WriteMode.READ_ONLY)
    allowed = ALLOWED_POINTS.get(site_id, [])
    if point_id not in allowed:
        from app.models.errors import api_error, ErrorCode
        raise api_error(
            ErrorCode.COMMAND_NOT_ALLOWED,
            f"Point {point_id} not on writeback allowlist",
            "النقطة غير مسموح بها للكتابة",
            status_code=403,
        )
    validate_write_request(
        user,
        mode=WriteMode.APPROVAL_REQUIRED,
        current_value=current_value,
        requested_value=requested_value,
        min_value=min_value,
        max_value=max_value,
        max_step=max_step,
    )
    if not approval_token:
        from app.models.errors import api_error, ErrorCode
        raise api_error(
            ErrorCode.COMMAND_NOT_ALLOWED,
            "Human approval token required",
            "رمز الموافقة البشرية مطلوب",
            status_code=403,
        )
    entry = {
        "site_id": site_id,
        "point_id": point_id,
        "current_value": current_value,
        "requested_value": requested_value,
        "actor": user.user_id,
        "approval_token": "***",
        "status": "QUEUED_NOT_EXECUTED",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    AUDIT_LOG.append(entry)
    return {
        **entry,
        "message": "Writeback request recorded — NOT executed (pilot READ_ONLY)",
        "executed": False,
    }
