"""In-memory session and audit event store (PDPL-safe — no raw email in logs)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional
from uuid import uuid4

_events: List[Dict[str, Any]] = []
_lock = Lock()
MAX_EVENTS = 5000


def _anonymize_email(email: Optional[str]) -> str:
    if not email:
        return "anonymous"
    return f"usr_{hashlib.sha256(email.lower().encode()).hexdigest()[:12]}"


def record_event(
    event_type: str,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    role: Optional[str] = None,
    module_path: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    event = {
        "id": str(uuid4()),
        "event_type": event_type,
        "user_ref": _anonymize_email(email) if email else (user_id or "anonymous"),
        "role": role,
        "module_path": module_path,
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        _events.append(event)
        if len(_events) > MAX_EVENTS:
            _events.pop(0)
    return event


def list_events(limit: int = 100, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    with _lock:
        items = list(_events)
    if event_type:
        items = [e for e in items if e["event_type"] == event_type]
    return list(reversed(items[-limit:]))


def session_stats() -> Dict[str, Any]:
    with _lock:
        items = list(_events)
    logins = [e for e in items if e["event_type"] == "login"]
    page_views = [e for e in items if e["event_type"] == "page_view"]
    unique_users = len({e["user_ref"] for e in items if e["user_ref"] != "anonymous"})
    return {
        "total_events": len(items),
        "total_logins": len(logins),
        "total_page_views": len(page_views),
        "unique_users": unique_users,
        "last_login": logins[-1]["timestamp"] if logins else None,
    }
