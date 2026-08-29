"""Immutable-style audit records for sensitive actions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("buildopt.audit")


def record_audit(
    *,
    actor: Optional[str],
    tenant: Optional[str],
    action: str,
    resource: str,
    result: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    entry = {
        "actor": actor,
        "tenant": tenant,
        "action": action,
        "resource": resource,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "metadata": metadata or {},
    }
    logger.info("audit %s", entry)
    return entry
