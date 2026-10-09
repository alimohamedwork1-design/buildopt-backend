"""Edge runtime configuration — secrets via environment only."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EdgeSettings:
    gateway_id: str
    tenant_id: str
    building_id: str
    cloud_api_url: str
    ingest_api_key: str
    gateway_api_key: str
    poll_interval_seconds: int
    queue_db_path: str
    connector: str
    metasys_host: str
    metasys_username: str
    metasys_password: str
    metasys_version: str
    mapped_points_file: str
    operating_mode: str = "hybrid"

    @property
    def api_key(self) -> str:
        """Prefer scoped GATEWAY_API_KEY (bo_gw_*) over shared INGEST_API_KEY."""
        return self.gateway_api_key or self.ingest_api_key

    @classmethod
    def from_env(cls) -> "EdgeSettings":
        mode = os.getenv("EDGE_OPERATING_MODE", "hybrid").strip().lower()
        if mode not in ("offline", "hybrid", "hybrid_4g"):
            raise ValueError("EDGE_OPERATING_MODE must be offline, hybrid or hybrid_4g")
        return cls(
            gateway_id=os.getenv("GATEWAY_ID", "edge-local-01"),
            tenant_id=os.getenv("TENANT_ID", "default"),
            building_id=os.getenv("BUILDING_ID", ""),
            cloud_api_url=os.getenv("CLOUD_API_URL", "https://buildopt-backend-production.up.railway.app").rstrip("/"),
            ingest_api_key=os.getenv("INGEST_API_KEY", ""),
            gateway_api_key=os.getenv("GATEWAY_API_KEY", ""),
            poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "30")),
            queue_db_path=os.getenv("EDGE_QUEUE_DB", "/data/edge_queue.db"),
            connector=os.getenv("EDGE_CONNECTOR", "metasys").lower(),
            metasys_host=os.getenv("METASYS_HOST", "").rstrip("/"),
            metasys_username=os.getenv("METASYS_USERNAME", ""),
            metasys_password=os.getenv("METASYS_PASSWORD", ""),
            metasys_version=os.getenv("METASYS_VERSION", "v4"),
            mapped_points_file=os.getenv("MAPPED_POINTS_FILE", "/config/mapped_points.json"),
            operating_mode=mode,
        )
