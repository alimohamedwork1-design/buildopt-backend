"""Privacy-safe incident metadata; does not collect exception messages or secrets."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


class ErrorSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class OperationalIncident:
    incident_id: str
    occurred_at: datetime
    severity: ErrorSeverity
    component: str
    error_code: str
    correlation_id: Optional[str]


def classify_operational_error(
    *, component: str, error_code: str, severity: ErrorSeverity,
    correlation_id: Optional[str] = None,
) -> OperationalIncident:
    for identifier in (component, error_code, correlation_id or "ok"):
        if len(identifier) > 80 or not identifier or not all(c.isalnum() or c in "_-." for c in identifier):
            raise ValueError("Identifiers must be bounded and contain no sensitive text")
    return OperationalIncident(
        incident_id=str(uuid4()), occurred_at=datetime.now(timezone.utc),
        severity=severity, component=component, error_code=error_code,
        correlation_id=correlation_id,
    )
