from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.services import demo_mode


class JCIMetasysClient:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        version: str = "v4",
        demo_mode: bool = True,
    ) -> None:
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.version = version
        self.demo_mode = demo_mode
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    def status(self) -> str:
        if self.demo_mode:
            return "simulated"
        if not self.host:
            return "not_configured"
        return "ready"

    async def _ensure_token(self) -> Optional[str]:
        if self.demo_mode:
            return "demo-token"

        now = datetime.now(timezone.utc)
        if self._token and self._token_expiry and now < self._token_expiry:
            return self._token

        if not self.host:
            return None

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.host}/api/{self.version}/login",
                json={"username": self.username, "password": self.password},
            )
            if response.status_code != 200:
                return None

            data = response.json()
            self._token = data.get("accessToken") or data.get("token")
            self._token_expiry = now + timedelta(minutes=14)
            return self._token

    async def _auth_headers(self) -> Dict[str, str]:
        token = await self._ensure_token()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    async def get_objects(self) -> List[Dict[str, Any]]:
        if self.demo_mode:
            return demo_mode.get_jci_objects()

        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{self.host}/api/{self.version}/objects", headers=headers)
            response.raise_for_status()
            return response.json()

    async def get_present_value(self, object_id: str) -> Any:
        if self.demo_mode:
            for obj in demo_mode.get_jci_objects():
                if obj["id"] == object_id:
                    return obj.get("present_value")
            return None

        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.host}/api/{self.version}/objects/{object_id}/attributes/presentValue",
                headers=headers,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def write_command(self, object_id: str, attribute: str, value: Any) -> bool:
        if self.demo_mode:
            return True

        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.patch(
                f"{self.host}/api/{self.version}/objects/{object_id}",
                headers=headers,
                json={"attributes": {attribute: value}},
            )
            return response.status_code in (200, 204)

    async def get_alarms(self) -> List[Dict[str, Any]]:
        if self.demo_mode:
            return demo_mode.get_jci_alarms()

        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{self.host}/api/{self.version}/alarms", headers=headers)
            response.raise_for_status()
            return response.json()

    async def get_trend(self, object_id: str) -> List[Dict[str, Any]]:
        if self.demo_mode:
            return demo_mode.get_jci_trend(object_id)

        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.host}/api/{self.version}/trends/{object_id}/trendedAttributes",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
