"""BMS adapter abstraction — protocol-specific logic stays behind this interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BMSConnector(ABC):
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def discover_devices(self) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def discover_equipment(self) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def discover_points(self) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def read_points(self, point_ids: List[str]) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def read_alarms(self) -> List[Dict[str, Any]]:
        ...

    async def write_point(self, point_id: str, value: Any, *, allowed: bool = False) -> Dict[str, Any]:
        if not allowed:
            return {"success": False, "reason": "write_disabled"}
        raise NotImplementedError("Write not implemented for this connector")


class MetasysConnector(BMSConnector):
    def __init__(self, client) -> None:
        self._client = client

    async def test_connection(self) -> Dict[str, Any]:
        return await self._client.health_probe()

    async def discover_devices(self) -> List[Dict[str, Any]]:
        return []

    async def discover_equipment(self) -> List[Dict[str, Any]]:
        return []

    async def discover_points(self) -> List[Dict[str, Any]]:
        return await self._client.get_objects()

    async def read_points(self, point_ids: List[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for pid in point_ids:
            out[pid] = await self._client.get_present_value(pid)
        return out

    async def read_alarms(self) -> List[Dict[str, Any]]:
        return await self._client.get_alarms()
