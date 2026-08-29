"""Johnson Controls Metasys REST connector — production pilot path."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.connectors.base import BuildingConnector, ConnectorError


class MetasysConnector(BuildingConnector):
    read_only = True

    def __init__(self, host: str, username: str, password: str, version: str = "v4") -> None:
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.version = version
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    async def capabilities(self) -> Dict[str, Any]:
        return {
            "historical_data": True,
            "alarms": True,
            "spaces": False,
            "equipment": False,
            "subscriptions": False,
            "writeback": False,
            "protocol": "metasys",
            "api_version": self.version,
        }

    async def _ensure_token(self) -> str:
        now = datetime.now(timezone.utc)
        if self._token and self._token_expiry and now < self._token_expiry:
            return self._token

        if not self.host or not self.username:
            raise ConnectorError("NOT_CONFIGURED", "Metasys host/username not configured")

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(
                    f"{self.host}/api/{self.version}/login",
                    json={"username": self.username, "password": self.password},
                )
        except httpx.ConnectError as exc:
            raise ConnectorError("CONNECTION_REFUSED", str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise ConnectorError("TIMEOUT", str(exc)) from exc

        if r.status_code == 401:
            raise ConnectorError("AUTH_ERROR", "Metasys authentication failed")
        if r.status_code >= 400:
            raise ConnectorError("API_ERROR", f"Login HTTP {r.status_code}")

        data = r.json()
        token = data.get("accessToken") or data.get("token")
        if not token:
            raise ConnectorError("API_ERROR", "No token in Metasys login response")
        self._token = token
        self._token_expiry = now + timedelta(minutes=14)
        return token

    async def connect(self) -> Dict[str, Any]:
        return await self.health()

    async def disconnect(self) -> None:
        self._token = None
        self._token_expiry = None

    async def health(self) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            await self._ensure_token()
            objects = await self.discover_objects()
            ms = int((time.perf_counter() - start) * 1000)
            return {
                "status": "ONLINE",
                "response_ms": ms,
                "object_count": len(objects),
                "connector": "metasys",
            }
        except ConnectorError as exc:
            ms = int((time.perf_counter() - start) * 1000)
            return {"status": exc.code, "response_ms": ms, "message": str(exc), "connector": "metasys"}

    async def discover_objects(self) -> List[Dict[str, Any]]:
        token = await self._ensure_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{self.host}/api/{self.version}/objects",
                headers={"Authorization": f"Bearer {token}"},
            )
            r.raise_for_status()
            payload = r.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("items") or payload.get("objects") or []
        return []

    async def read_point(self, point_id: str) -> Any:
        token = await self._ensure_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{self.host}/api/{self.version}/objects/{point_id}/attributes/presentValue",
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()

    async def get_alarms(self) -> List[Dict[str, Any]]:
        token = await self._ensure_token()
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                f"{self.host}/api/{self.version}/alarms",
                headers={"Authorization": f"Bearer {token}"},
            )
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else data.get("items", [])
