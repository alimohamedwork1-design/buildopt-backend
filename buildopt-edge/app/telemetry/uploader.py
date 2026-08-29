"""Cloud upload — batch telemetry + heartbeat."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from app.config import EdgeSettings


class CloudUploader:
    def __init__(self, settings: EdgeSettings) -> None:
        self.settings = settings

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.ingest_api_key:
            headers["X-API-Key"] = self.settings.ingest_api_key
        return headers

    async def upload_batch(self, readings: List[Dict[str, Any]], queue_depth: int = 0) -> bool:
        payload = {
            "gateway_id": self.settings.gateway_id,
            "tenant_id": self.settings.tenant_id,
            "building_id": self.settings.building_id,
            "readings": readings,
        }
        url = f"{self.settings.cloud_api_url}/api/v1/telemetry/batch"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload, headers=self._headers())
            if r.status_code == 200:
                await self.send_heartbeat(
                    connector_status="ONLINE",
                    telemetry_rate=len(readings),
                    queue_depth=queue_depth,
                )
                return True
            return False

    async def send_heartbeat(
        self,
        *,
        connector_status: str,
        telemetry_rate: int = 0,
        queue_depth: int = 0,
        connector_error: str | None = None,
    ) -> None:
        payload = {
            "gateway_id": self.settings.gateway_id,
            "tenant_id": self.settings.tenant_id,
            "building_id": self.settings.building_id,
            "protocol": self.settings.connector,
            "version": "1.0.0",
            "connector_status": connector_status,
            "telemetry_rate": telemetry_rate,
            "queue_depth": queue_depth,
            "last_read_at": datetime.now(timezone.utc).isoformat(),
            "connector_error": connector_error,
        }
        url = f"{self.settings.cloud_api_url}/api/v1/gateways/heartbeat"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json=payload, headers=self._headers())
        except Exception:
            pass
