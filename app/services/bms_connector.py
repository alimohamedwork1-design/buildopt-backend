"""Vendor-neutral BMS connector abstraction — READ ONLY for pilot phase."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional


class BMSConnector(ABC):
    read_only: bool = True

    @abstractmethod
    async def connect(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def discover_sites(self) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def discover_spaces(self, site_id: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def discover_equipment(self, site_id: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def discover_objects(self) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def get_object(self, object_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def get_present_value(self, object_id: str) -> Any:
        ...

    @abstractmethod
    async def get_trend_data(self, object_id: str, *, hours: int = 24) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def get_alarms(self) -> List[Dict[str, Any]]:
        ...

    async def subscribe_telemetry(self, object_ids: List[str], callback: Callable[..., Any]) -> Dict[str, Any]:
        return {"subscribed": False, "reason": "not_implemented"}

    async def write_value(self, object_id: str, value: Any, *, allowed: bool = False) -> Dict[str, Any]:
        if not allowed or self.read_only:
            return {"success": False, "reason": "write_disabled_pilot_read_only"}
        raise NotImplementedError("Write gated — not enabled for pilot")

    async def validate_write(self, object_id: str, value: Any) -> Dict[str, Any]:
        return {"valid": False, "reason": "write_disabled_pilot_read_only"}

    async def test_connection(self) -> Dict[str, Any]:
        return await self.health()


class MetasysConnector(BMSConnector):
    read_only = True

    def __init__(self, client) -> None:
        self._client = client

    async def connect(self) -> Dict[str, Any]:
        probe = await self._client.health_probe()
        return {"status": probe.get("status", "unknown"), **probe}

    async def disconnect(self) -> None:
        return None

    async def health(self) -> Dict[str, Any]:
        return await self._client.health_probe()

    async def discover_sites(self) -> List[Dict[str, Any]]:
        return []

    async def discover_spaces(self, site_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    async def discover_equipment(self, site_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    async def discover_objects(self) -> List[Dict[str, Any]]:
        return await self._client.get_objects()

    async def get_object(self, object_id: str) -> Dict[str, Any]:
        val = await self._client.get_present_value(object_id)
        return {"id": object_id, "present_value": val}

    async def get_present_value(self, object_id: str) -> Any:
        return await self._client.get_present_value(object_id)

    async def get_trend_data(self, object_id: str, *, hours: int = 24) -> List[Dict[str, Any]]:
        return await self._client.get_trend(object_id)

    async def get_alarms(self) -> List[Dict[str, Any]]:
        return await self._client.get_alarms()

    async def write_value(self, object_id: str, value: Any, *, allowed: bool = False) -> Dict[str, Any]:
        return await super().write_value(object_id, value, allowed=allowed)
