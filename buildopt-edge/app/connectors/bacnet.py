"""Protocol placeholders — BETA / PLANNED states only."""

from __future__ import annotations

from typing import Any, Dict, List

from app.connectors.base import BuildingConnector


class _PlaceholderConnector(BuildingConnector):
    def __init__(self, protocol: str, state: str = "PLANNED") -> None:
        self.protocol = protocol
        self.state = state

    async def connect(self) -> Dict[str, Any]:
        return {"status": self.state, "protocol": self.protocol}

    async def disconnect(self) -> None:
        return None

    async def health(self) -> Dict[str, Any]:
        return {"status": self.state, "protocol": self.protocol}

    async def capabilities(self) -> Dict[str, Any]:
        return {
            "historical_data": False,
            "alarms": False,
            "spaces": False,
            "equipment": False,
            "subscriptions": False,
            "writeback": False,
            "protocol": self.protocol,
            "state": self.state,
        }

    async def discover_objects(self) -> List[Dict[str, Any]]:
        return []

    async def read_point(self, point_id: str) -> Any:
        return None


class BacnetConnector(_PlaceholderConnector):
    def __init__(self) -> None:
        super().__init__("bacnet", "BETA")
