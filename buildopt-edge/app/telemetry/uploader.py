"""Cloud upload — batch telemetry, discovery sync, heartbeat with replay metrics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.config import EdgeSettings
from app.storage.collection_config_cache import (
    load_cached_config,
    save_cached_config,
    validate_cloud_config,
)


class CloudUploader:
    def __init__(self, settings: EdgeSettings) -> None:
        self.settings = settings
        self.events_uploaded_total = 0
        self.events_queued_total = 0
        self.events_replayed_total = 0
        self.upload_failures_total = 0
        self.last_successful_upload_at: Optional[str] = None
        self._upload_timestamps: List[float] = []
        self._active_config_version: Optional[str] = None
        self._config_refresh_failures = 0
        cached_mapping, cached_version = load_cached_config(settings.queue_db_path)
        if cached_mapping:
            self._active_config_version = cached_version

    def load_cached_mapping(self) -> Dict[str, str]:
        mapping, version = load_cached_config(self.settings.queue_db_path)
        if version:
            self._active_config_version = version
        return mapping

    def _persist_config(self, mapping: Dict[str, str], config_version: Optional[str]) -> None:
        save_cached_config(
            self.settings.queue_db_path,
            mapping=mapping,
            config_version=config_version,
        )
        if config_version:
            self._active_config_version = config_version

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.api_key:
            headers["X-API-Key"] = self.settings.api_key
        return headers

    async def fetch_collection_config(self) -> Dict[str, str]:
        """Load approved mapping + version from cloud; validate and persist on success."""
        if not self.settings.api_key:
            return {}
        url = f"{self.settings.cloud_api_url}/api/v1/gateways/{self.settings.gateway_id}/collection-config"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=self._headers())
            if r.status_code in (401, 403):
                self._config_refresh_failures += 1
                return {}
            if r.status_code != 200:
                self._config_refresh_failures += 1
                return {}
            body = r.json()
            mapping, version = validate_cloud_config(body)
            if not mapping:
                self._config_refresh_failures += 1
                return {}
            if version and version == self._active_config_version:
                return mapping
            self._persist_config(mapping, version)
            return mapping

    def _telemetry_rate_per_minute(self) -> float:
        now = datetime.now(timezone.utc).timestamp()
        self._upload_timestamps = [t for t in self._upload_timestamps if now - t <= 60]
        return float(len(self._upload_timestamps))

    async def sync_discovery(self, points: List[Dict[str, Any]]) -> bool:
        if not points:
            return True
        payload = {
            "gateway_id": self.settings.gateway_id,
            "tenant_id": self.settings.tenant_id,
            "building_id": self.settings.building_id,
            "connector_id": self.settings.connector,
            "points": points,
        }
        url = f"{self.settings.cloud_api_url}/api/v1/discovery/points/batch"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload, headers=self._headers())
            return r.status_code == 200

    async def upload_batch(
        self,
        readings: List[Dict[str, Any]],
        *,
        queue_depth: int = 0,
        oldest_queued_event_seconds: Optional[int] = None,
        replay: bool = False,
    ) -> bool:
        payload = {
            "gateway_id": self.settings.gateway_id,
            "tenant_id": self.settings.tenant_id,
            "building_id": self.settings.building_id,
            "connector_id": self.settings.connector,
            "readings": readings,
        }
        url = f"{self.settings.cloud_api_url}/api/v1/telemetry/batch"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload, headers=self._headers())
            if r.status_code == 200:
                body = r.json()
                accepted = int(body.get("accepted", 0))
                if replay:
                    self.events_replayed_total += accepted
                else:
                    self.events_uploaded_total += accepted
                self.last_successful_upload_at = datetime.now(timezone.utc).isoformat()
                self._upload_timestamps.append(datetime.now(timezone.utc).timestamp())
                await self.send_heartbeat(
                    connector_status="ONLINE",
                    telemetry_rate=accepted,
                    queue_depth=queue_depth,
                    oldest_queued_event_seconds=oldest_queued_event_seconds,
                )
                return True
            self.upload_failures_total += 1
            return False

    async def send_heartbeat(
        self,
        *,
        connector_status: str,
        telemetry_rate: int = 0,
        queue_depth: int = 0,
        oldest_queued_event_seconds: Optional[int] = None,
        connector_error: str | None = None,
    ) -> None:
        edge_now = datetime.now(timezone.utc)
        payload = {
            "gateway_id": self.settings.gateway_id,
            "tenant_id": self.settings.tenant_id,
            "building_id": self.settings.building_id,
            "connector_id": self.settings.connector,
            "protocol": self.settings.connector,
            "version": "1.0.0",
            "connector_status": connector_status,
            "telemetry_rate": telemetry_rate,
            "queue_depth": queue_depth,
            "oldest_queued_event_seconds": oldest_queued_event_seconds,
            "events_uploaded_total": self.events_uploaded_total,
            "events_queued_total": self.events_queued_total,
            "events_replayed_total": self.events_replayed_total,
            "upload_failures_total": self.upload_failures_total,
            "last_successful_upload_at": self.last_successful_upload_at,
            "telemetry_rate_per_minute": self._telemetry_rate_per_minute(),
            "edge_clock_at": edge_now.isoformat(),
            "connector_error": connector_error,
        }
        url = f"{self.settings.cloud_api_url}/api/v1/gateways/heartbeat"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json=payload, headers=self._headers())
        except Exception:
            pass
