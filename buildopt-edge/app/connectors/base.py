"""Vendor-neutral building connector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional


class BuildingConnector(ABC):
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
    async def capabilities(self) -> Dict[str, Any]:
        ...

    async def discover_sites(self) -> List[Dict[str, Any]]:
        return []

    async def discover_spaces(self, site_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    async def discover_equipment(self, site_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    async def discover_points(self) -> List[Dict[str, Any]]:
        return await self.discover_objects()

    @abstractmethod
    async def discover_objects(self) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def read_point(self, point_id: str) -> Any:
        ...

    async def read_points(self, point_ids: List[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for pid in point_ids:
            try:
                out[pid] = await self.read_point(pid)
            except Exception as exc:
                out[pid] = {"error": str(exc)}
        return out

    async def read_history(self, point_id: str, start: str, end: str) -> List[Dict[str, Any]]:
        return []

    async def get_alarms(self) -> List[Dict[str, Any]]:
        return []

    async def subscribe(self, point_ids: List[str], callback: Callable[..., Any]) -> Dict[str, Any]:
        return {"subscribed": False, "reason": "not_implemented"}

    async def write_value(self, point_id: str, value: Any) -> Dict[str, Any]:
        if self.read_only:
            return {"success": False, "reason": "write_disabled_pilot_read_only"}
        raise NotImplementedError("Write gated for pilot")


class ConnectorError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
