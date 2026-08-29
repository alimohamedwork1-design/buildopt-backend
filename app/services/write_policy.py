"""Safe write-back policy — disabled by default."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from app.models.errors import ErrorCode, api_error
from app.models.user_context import UserContext


class WriteMode(str, Enum):
    READ_ONLY = "READ_ONLY"
    ADVISORY = "ADVISORY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    AUTOMATIC = "AUTOMATIC"


DEFAULT_WRITE_MODE = WriteMode.READ_ONLY


def validate_write_request(
    user: UserContext,
    *,
    mode: WriteMode = DEFAULT_WRITE_MODE,
    current_value: Optional[float] = None,
    requested_value: Optional[float] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    max_step: Optional[float] = None,
) -> None:
    if mode == WriteMode.READ_ONLY:
        raise api_error(
            ErrorCode.COMMAND_NOT_ALLOWED,
            "Write-back is disabled (READ_ONLY mode)",
            "الكتابة معطلة (وضع القراءة فقط)",
            status_code=403,
        )
    if user.is_read_only:
        raise api_error(
            ErrorCode.PERMISSION_DENIED,
            "Read-only account cannot issue commands",
            "حساب القراءة فقط لا يمكنه إرسال أوامر",
            status_code=403,
        )
    if requested_value is None:
        raise api_error(
            ErrorCode.VALIDATION_ERROR,
            "Requested value is required",
            "القيمة المطلوبة مطلوبة",
            status_code=422,
        )
    if min_value is not None and requested_value < min_value:
        raise api_error(
            ErrorCode.VALIDATION_ERROR,
            f"Value below minimum ({min_value})",
            f"القيمة أقل من الحد الأدنى ({min_value})",
            status_code=422,
        )
    if max_value is not None and requested_value > max_value:
        raise api_error(
            ErrorCode.VALIDATION_ERROR,
            f"Value above maximum ({max_value})",
            f"القيمة أعلى من الحد الأقصى ({max_value})",
            status_code=422,
        )
    if (
        max_step is not None
        and current_value is not None
        and abs(requested_value - current_value) > max_step
    ):
        raise api_error(
            ErrorCode.VALIDATION_ERROR,
            f"Step change exceeds limit ({max_step})",
            f"تجاوز التغيير الحد المسموح ({max_step})",
            status_code=422,
        )


def write_mode_metadata(mode: WriteMode = DEFAULT_WRITE_MODE) -> Dict[str, Any]:
    return {"write_mode": mode.value, "write_enabled": mode != WriteMode.READ_ONLY}
