"""Semantic mapping audit trail — dedicated store, not generic logs."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SemanticAuditStore:
    """Audit events backed by telemetry store semantic_audit_log table."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def record(
        self,
        *,
        point_id: Optional[str],
        building_id: str,
        action: str,
        previous_state: Dict[str, Any],
        new_state: Dict[str, Any],
        source_point_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        gateway_id: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        comment: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        audit_id = secrets.token_hex(12)
        return self._store.insert_semantic_audit(
            audit_id=audit_id,
            point_id=point_id,
            building_id=building_id,
            tenant_id=tenant_id,
            gateway_id=gateway_id,
            source_point_id=source_point_id,
            action=action,
            previous_state=previous_state,
            new_state=new_state,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            comment=comment,
            confidence=confidence,
        )

    def list_for_point(self, point_id: str, *, limit: int = 50) -> List[Dict[str, Any]]:
        return self._store.list_semantic_audit(point_id=point_id, limit=limit)

    def list_for_building(self, building_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
        return self._store.list_semantic_audit(building_id=building_id, limit=limit)


_store: Optional[SemanticAuditStore] = None


def get_semantic_audit_store() -> SemanticAuditStore:
    global _store
    if _store is None:
        from app.services.telemetry_store import get_telemetry_store

        _store = SemanticAuditStore(get_telemetry_store())
    return _store


def reset_semantic_audit_store(store: Optional[SemanticAuditStore] = None) -> None:
    global _store
    _store = store
