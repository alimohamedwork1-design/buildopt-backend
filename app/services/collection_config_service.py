"""Collection config versioning — DRAFT / ACTIVE / SUPERSEDED."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.semantic_mapping_service import build_collection_config


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CollectionConfigService:
    def __init__(self, store: Any) -> None:
        self._store = store

    def publish(
        self,
        *,
        building_id: str,
        gateway_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        activate: bool = True,
    ) -> Dict[str, Any]:
        points, _ = self._store.list_points(building_id=building_id, gateway_id=gateway_id, limit=500)
        config = build_collection_config(points, building_id=building_id, gateway_id=gateway_id)
        approved_count = len(config.get("points") or [])
        unmapped = sum(
            1 for p in points
            if (p.get("metadata") or {}).get("mapping_status") not in ("APPROVED", "REJECTED")
        )
        revision = self._store.next_mapping_revision(building_id, gateway_id)
        config_version = f"cfg_{building_id[:8]}_{revision}_{secrets.token_hex(4)}"
        if activate and approved_count > 0:
            row = self._store.publish_active_config_version(
                config_version=config_version,
                building_id=building_id,
                gateway_id=gateway_id,
                tenant_id=tenant_id,
                mapping_revision=revision,
                point_count=len(points),
                approved_count=approved_count,
                config_payload=config,
                activated_at=_utcnow(),
            )
            status = "ACTIVE"
        else:
            row = self._store.insert_config_version(
                config_version=config_version,
                building_id=building_id,
                gateway_id=gateway_id,
                tenant_id=tenant_id,
                mapping_revision=revision,
                point_count=len(points),
                approved_count=approved_count,
                status="DRAFT",
                config_payload=config,
                activated_at=None,
            )
            status = "DRAFT"
        return {
            **config,
            "config_version": config_version,
            "mapping_revision": revision,
            "status": status,
            "point_count": len(points),
            "approved_count": approved_count,
            "unmapped_count": unmapped,
            "published_at": row.get("created_at"),
        }

    def get_active(
        self,
        *,
        building_id: str,
        gateway_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        row = self._store.get_active_config_version(building_id, gateway_id)
        if not row:
            return None
        payload = row.get("config_payload") or {}
        return {
            **payload,
            "config_version": row["config_version"],
            "mapping_revision": row["mapping_revision"],
            "status": row["status"],
            "point_count": row.get("point_count", 0),
            "approved_count": row.get("approved_count", 0),
            "published_at": row.get("activated_at") or row.get("created_at"),
        }

    def list_versions(self, building_id: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        return self._store.list_config_versions(building_id, limit=limit)


_service: Optional[CollectionConfigService] = None


def get_collection_config_service() -> CollectionConfigService:
    global _service
    if _service is None:
        from app.services.telemetry_store import get_telemetry_store

        _service = CollectionConfigService(get_telemetry_store())
    return _service


def reset_collection_config_service(svc: Optional[CollectionConfigService] = None) -> None:
    global _service
    _service = svc
