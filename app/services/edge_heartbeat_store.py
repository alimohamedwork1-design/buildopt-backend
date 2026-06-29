"""In-memory edge agent heartbeat tracking (per building + protocol)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class EdgeHeartbeatStore:
    def __init__(self) -> None:
        self._beats: Dict[str, Dict[str, Any]] = {}

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

    def get(self, protocol: str) -> Optional[Dict[str, Any]]:
        latest: Optional[Dict[str, Any]] = None
        for beat in self._beats.values():
            if beat["protocol"] != protocol:
                continue
            if latest is None or beat["last_read_at"] > latest["last_read_at"]:
                latest = beat
        return latest

    def status(self, protocol: str, stale_seconds: int = 120) -> str:
        beat = self.get(protocol)
        if not beat:
            return "not_configured"
        age = (datetime.now(timezone.utc) - beat["last_read_at"]).total_seconds()
        return "connected" if age <= stale_seconds else "disconnected"


edge_heartbeat_store = EdgeHeartbeatStore()
