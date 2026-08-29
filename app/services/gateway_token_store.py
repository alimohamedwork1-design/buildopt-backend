"""Per-gateway scoped ingest tokens — replaces shared INGEST_API_KEY on edge hosts."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import get_settings


def _hash_token(token: str) -> str:
    settings = get_settings()
    pepper = settings.secret_key or "buildopt"
    return hashlib.sha256(f"{pepper}:{token}".encode()).hexdigest()


def _token_prefix(gateway_id: str) -> str:
    safe = gateway_id.replace(" ", "-")[:32]
    return f"bo_gw_{safe}_"


class GatewayTokenStore:
    """Token lifecycle backed by telemetry store gateway_tokens table."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def issue(
        self,
        *,
        gateway_id: str,
        label: str = "edge",
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        token_plain = _token_prefix(gateway_id) + secrets.token_urlsafe(24)
        token_id = secrets.token_hex(8)
        row = self._store.create_gateway_token(
            token_id=token_id,
            gateway_id=gateway_id,
            token_hash=_hash_token(token_plain),
            label=label,
            expires_at=expires_at,
        )
        return {**row, "token": token_plain}

    def validate(self, token_plain: str) -> Optional[str]:
        if not token_plain or not token_plain.startswith("bo_gw_"):
            return None
        token_hash = _hash_token(token_plain)
        row = self._store.get_gateway_token_by_hash(token_hash)
        if not row or row.get("revoked_at"):
            return None
        expires = row.get("expires_at")
        if expires:
            try:
                exp = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp < datetime.now(timezone.utc):
                    return None
            except (ValueError, TypeError):
                pass
        return row.get("gateway_id")

    def revoke(self, token_id: str) -> bool:
        return self._store.revoke_gateway_token(token_id)

    def list_for_gateway(self, gateway_id: str) -> List[Dict[str, Any]]:
        return self._store.list_gateway_tokens(gateway_id)


_store: Optional[GatewayTokenStore] = None


def get_gateway_token_store() -> GatewayTokenStore:
    global _store
    if _store is None:
        from app.services.telemetry_store import get_telemetry_store

        _store = GatewayTokenStore(get_telemetry_store())
    return _store


def reset_gateway_token_store(store: Optional[GatewayTokenStore] = None) -> None:
    global _store
    _store = store
