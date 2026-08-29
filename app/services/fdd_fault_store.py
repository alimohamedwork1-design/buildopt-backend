"""FDD fault persistence with lifecycle and deduplication."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


FAULT_STATUSES = ("DETECTED", "INVESTIGATING", "CONFIRMED", "SUPPRESSED", "RESOLVED", "CLOSED")


class FddFaultStore:
    def __init__(self, store: Any) -> None:
        self._store = store

    def upsert_fault(self, fault: Dict[str, Any]) -> Dict[str, Any]:
        existing = self._store.get_fdd_fault(fault["fault_id"])
        now = datetime.now(timezone.utc).isoformat()
        if existing:
            merged = {**existing, **fault, "last_seen": now, "updated_at": now}
            if existing.get("status") not in ("RESOLVED", "CLOSED"):
                merged["first_seen"] = existing.get("first_seen", now)
            return self._store.upsert_fdd_fault(merged)
        fault.setdefault("first_seen", now)
        fault.setdefault("detected_at", now)
        fault.setdefault("last_seen", now)
        fault.setdefault("status", "DETECTED")
        return self._store.upsert_fdd_fault(fault)

    def transition(
        self,
        fault_id: str,
        *,
        new_status: str,
        actor_user_id: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if new_status not in FAULT_STATUSES:
            raise ValueError("invalid_fault_status")
        existing = self._store.get_fdd_fault(fault_id)
        if not existing:
            return None
        prev = existing.get("status")
        updated = self._store.upsert_fdd_fault({
            **existing,
            "status": new_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": datetime.now(timezone.utc).isoformat() if new_status in ("RESOLVED", "CLOSED") else existing.get("resolved_at"),
        })
        self._store.insert_fdd_fault_audit(
            audit_id=secrets.token_hex(12),
            fault_id=fault_id,
            action="STATUS_CHANGE",
            previous_status=prev,
            new_status=new_status,
            actor_user_id=actor_user_id,
            comment=comment,
        )
        return updated

    def list_active(self, building_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
        return self._store.list_fdd_faults(building_id=building_id, active_only=True, limit=limit)

    def list_all(self, building_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
        return self._store.list_fdd_faults(building_id=building_id, active_only=False, limit=limit)


_store: Optional[FddFaultStore] = None


def get_fdd_fault_store() -> FddFaultStore:
    global _store
    if _store is None:
        from app.services.telemetry_store import get_telemetry_store

        _store = FddFaultStore(get_telemetry_store())
    return _store


def reset_fdd_fault_store(s: Optional[FddFaultStore] = None) -> None:
    global _store
    _store = s
