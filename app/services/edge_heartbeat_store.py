"""In-memory edge agent + gateway heartbeat tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class EdgeHeartbeatStore:
    def __init__(self) -> None:
        self._beats: Dict[str, Dict[str, Any]] = {}
        self._gateways: Dict[str, Dict[str, Any]] = {}

    def record(
        self,
        building_id: str,
        protocol: str,
        last_read_at: Optional[datetime] = None,
        data_points: int = 0,
    ) -> None:
        key = f"{building_id}:{protocol}"
        self._beats[key] = {
            "building_id": building_id,
            "protocol": protocol,
            "last_read_at": last_read_at or datetime.now(timezone.utc),
            "data_points": data_points,
        }

    def record_gateway(
        self,
        *,
        gateway_id: str,
        building_id: str,
        tenant_id: Optional[str] = None,
        protocol: str = "edge",
        connector_id: str = "metasys",
        version: str = "1.0.0",
        connector_status: str = "ONLINE",
        telemetry_rate: int = 0,
        queue_depth: int = 0,
        oldest_queued_event_seconds: Optional[int] = None,
        events_uploaded_total: int = 0,
        events_queued_total: int = 0,
        events_replayed_total: int = 0,
        upload_failures_total: int = 0,
        last_successful_upload_at: Optional[datetime] = None,
        telemetry_rate_per_minute: float = 0.0,
        clock_drift_seconds: Optional[int] = None,
        edge_clock_at: Optional[datetime] = None,
        connector_error: Optional[str] = None,
        last_read_at: Optional[datetime] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        existing = self._gateways.get(gateway_id, {})
        self._gateways[gateway_id] = {
            "gateway_id": gateway_id,
            "tenant_id": tenant_id,
            "building_id": building_id,
            "protocol": protocol,
            "connector_id": connector_id,
            "version": version,
            "connector_status": connector_status,
            "telemetry_rate": telemetry_rate,
            "queue_depth": queue_depth,
            "oldest_queued_event_seconds": oldest_queued_event_seconds,
            "events_uploaded_total": events_uploaded_total or existing.get("events_uploaded_total", 0),
            "events_queued_total": events_queued_total or existing.get("events_queued_total", 0),
            "events_replayed_total": events_replayed_total or existing.get("events_replayed_total", 0),
            "upload_failures_total": upload_failures_total or existing.get("upload_failures_total", 0),
            "last_successful_upload_at": last_successful_upload_at or existing.get("last_successful_upload_at"),
            "telemetry_rate_per_minute": telemetry_rate_per_minute,
            "clock_drift_seconds": clock_drift_seconds,
            "edge_clock_at": edge_clock_at.isoformat() if edge_clock_at else existing.get("edge_clock_at"),
            "last_seen": now,
            "last_read_at": last_read_at or now,
            "connector_error": connector_error,
        }
        self.record(building_id, protocol, last_read_at or now, telemetry_rate)

    def get(self, protocol: str) -> Optional[Dict[str, Any]]:
        latest: Optional[Dict[str, Any]] = None
        for beat in self._beats.values():
            if beat["protocol"] != protocol:
                continue
            if latest is None or beat["last_read_at"] > latest["last_read_at"]:
                latest = beat
        return latest

    def get_gateway(self, gateway_id: str) -> Optional[Dict[str, Any]]:
        return self._gateways.get(gateway_id)

    def list_gateways(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for gw in self._gateways.values():
            age = (now - gw["last_seen"]).total_seconds()
            state = gw["connector_status"]
            if state in ("ONLINE", "DEGRADED") and age > 120:
                state = "STALE"
            if age > 600:
                state = "OFFLINE"
            last_upload = gw.get("last_successful_upload_at")
            if isinstance(last_upload, datetime):
                last_upload = last_upload.isoformat()
            out.append(
                {
                    **gw,
                    "state": state,
                    "freshness_seconds": int(age),
                    "last_successful_upload_at": last_upload,
                }
            )
        return sorted(out, key=lambda g: g["gateway_id"])

    def status(self, protocol: str, stale_seconds: int = 120) -> str:
        beat = self.get(protocol)
        if not beat:
            return "not_configured"
        age = (datetime.now(timezone.utc) - beat["last_read_at"]).total_seconds()
        return "connected" if age <= stale_seconds else "disconnected"


edge_heartbeat_store = EdgeHeartbeatStore()
