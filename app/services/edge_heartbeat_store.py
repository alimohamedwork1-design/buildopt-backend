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
        version: str = "1.0.0",
        connector_status: str = "ONLINE",
        telemetry_rate: int = 0,
        queue_depth: int = 0,
        last_read_at: Optional[datetime] = None,
        connector_error: Optional[str] = None,
    ) -> None:
        now = last_read_at or datetime.now(timezone.utc)
        self._gateways[gateway_id] = {
            "gateway_id": gateway_id,
            "tenant_id": tenant_id,
            "building_id": building_id,
            "protocol": protocol,
            "version": version,
            "connector_status": connector_status,
            "telemetry_rate": telemetry_rate,
            "queue_depth": queue_depth,
            "last_seen": now,
            "last_read_at": now,
            "connector_error": connector_error,
        }
        self.record(building_id, protocol, now, telemetry_rate)

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
            if state == "ONLINE" and age > 120:
                state = "STALE"
            if age > 600:
                state = "OFFLINE"
            out.append({**gw, "state": state, "freshness_seconds": int(age)})
        return sorted(out, key=lambda g: g["gateway_id"])

    def status(self, protocol: str, stale_seconds: int = 120) -> str:
        beat = self.get(protocol)
        if not beat:
            return "not_configured"
        age = (datetime.now(timezone.utc) - beat["last_read_at"]).total_seconds()
        return "connected" if age <= stale_seconds else "disconnected"


edge_heartbeat_store = EdgeHeartbeatStore()
