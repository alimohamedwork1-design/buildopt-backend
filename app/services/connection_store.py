from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger("buildopt.jci")


@dataclass
class MetasysCredentials:
    host: str
    username: str
    password: str
    version: str = "v4"
    status: str = "disconnected"
    last_connected_at: Optional[datetime] = None


def _fernet(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _encrypt_password(password: str, secret: str) -> str:
    return _fernet(secret).encrypt(password.encode()).decode()


def _decrypt_password(token: str, secret: str) -> str:
    try:
        return _fernet(secret).decrypt(token.encode()).decode()
    except InvalidToken:
        return ""


class ConnectionStore:
    def __init__(self) -> None:
        self._metasys: Optional[MetasysCredentials] = None

    def get_metasys(self) -> MetasysCredentials:
        if self._metasys:
            return self._metasys
        settings = get_settings()
        return MetasysCredentials(
            host=settings.jci_metasys_host,
            username=settings.jci_metasys_username,
            password=settings.jci_metasys_password,
            version=settings.jci_metasys_version,
            status="connected" if settings.jci_metasys_host else "disconnected",
        )

    def has_saved_metasys(self) -> bool:
        creds = self.get_metasys()
        return bool(creds.host and creds.username)

    def update_metasys(
        self,
        host: str,
        username: str,
        password: str,
        version: str = "v4",
        *,
        status: str = "connected",
    ) -> MetasysCredentials:
        now = datetime.now(timezone.utc)
        self._metasys = MetasysCredentials(
            host=host.rstrip("/"),
            username=username,
            password=password,
            version=version,
            status=status,
            last_connected_at=now,
        )
        return self._metasys

    async def save_metasys(
        self,
        host: str,
        username: str,
        password: str,
        version: str = "v4",
    ) -> Dict[str, Any]:
        settings = get_settings()
        creds = self.update_metasys(host, username, password, version, status="connected")
        encrypted = _encrypt_password(password, settings.secret_key)

        saved_remote = await self._persist_supabase(
            protocol="metasys",
            host=creds.host,
            username=username,
            password_encrypted=encrypted,
            version=version,
        )

        logger.info(
            "Metasys credentials saved for %s (supabase=%s)",
            creds.host,
            "yes" if saved_remote else "memory-only",
        )
        return {
            "status": "saved",
            "message": "Metasys credentials saved. Live data will begin within 30 seconds.",
            "message_ar": "تم حفظ بيانات Metasys. ستبدأ البيانات الحية خلال 30 ثانية.",
            "supabase_persisted": saved_remote,
        }

    async def _persist_supabase(
        self,
        *,
        protocol: str,
        host: str,
        username: str,
        password_encrypted: str,
        version: str,
    ) -> bool:
        settings = get_settings()
        if not settings.supabase_url:
            return False

        row = {
            "protocol": protocol,
            "host": host,
            "username": username,
            "password_encrypted": password_encrypted,
            "version": version,
            "status": "connected",
            "last_connected_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        auth_key = settings.supabase_service_key or settings.supabase_key
        if not auth_key:
            return False

        headers = {
            "apikey": auth_key,
            "Authorization": f"Bearer {auth_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }
        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/bms_connections"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=row,
                    params={"on_conflict": "protocol"},
                )
                if response.status_code in (200, 201, 204):
                    return True
                if response.status_code == 404:
                    logger.warning("bms_connections table missing — save in-memory only")
                return False
        except Exception as exc:
            logger.warning("Supabase bms_connections save failed: %s", exc)
            return False

    async def load_metasys_from_supabase(self) -> None:
        settings = get_settings()
        auth_key = settings.supabase_service_key or settings.supabase_key
        if not settings.supabase_url or not auth_key:
            return

        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/bms_connections"
        params = {"protocol": "eq.metasys", "select": "*", "limit": "1"}
        headers = {"apikey": auth_key, "Authorization": f"Bearer {auth_key}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, params=params)
                if response.status_code != 200:
                    return
                rows = response.json()
                if not rows:
                    return
                row = rows[0]
                password = _decrypt_password(row.get("password_encrypted", ""), settings.secret_key)
                if not password:
                    return
                self.update_metasys(
                    row.get("host", ""),
                    row.get("username", ""),
                    password,
                    row.get("version", "v4"),
                    status=row.get("status", "connected"),
                )
        except Exception as exc:
            logger.warning("Could not load Metasys credentials from Supabase: %s", exc)


connection_store = ConnectionStore()
