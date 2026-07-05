from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

import httpx

from app.config import get_settings
from app.models.user_context import UserContext

logger = logging.getLogger("buildopt.account")

DEFAULT_MODULES = {
    "overview", "telemetry", "alerts", "equipment", "energy", "compliance",
    "fdd", "settings", "bms-settings", "system-status",
}


async def fetch_user_context(token: str) -> Optional[UserContext]:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        return None

    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {token}",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            user_resp = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers=headers,
            )
            if user_resp.status_code != 200:
                return None
            user = user_resp.json()
            user_id = user.get("id")
            email = user.get("email")
            if not user_id:
                return None

            svc_key = settings.supabase_service_key or settings.supabase_key
            svc_headers = {"apikey": svc_key, "Authorization": f"Bearer {svc_key}"}

            profile_resp = await client.get(
                f"{settings.supabase_url.rstrip('/')}/rest/v1/profiles",
                headers=svc_headers,
                params={"user_id": f"eq.{user_id}", "select": "account_mode,access_level,account_status"},
            )
            profile: Dict[str, Any] = {}
            if profile_resp.status_code == 200 and profile_resp.json():
                profile = profile_resp.json()[0]

            roles_resp = await client.get(
                f"{settings.supabase_url.rstrip('/')}/rest/v1/user_roles",
                headers=svc_headers,
                params={"user_id": f"eq.{user_id}", "select": "role"},
            )
            roles: List[str] = []
            if roles_resp.status_code == 200:
                roles = [r["role"] for r in roles_resp.json()]

            buildings_resp = await client.get(
                f"{settings.supabase_url.rstrip('/')}/rest/v1/buildings",
                headers=svc_headers,
                params={"owner_id": f"eq.{user_id}", "select": "id"},
            )
            building_ids: List[str] = []
            if buildings_resp.status_code == 200:
                building_ids = [str(b["id"]) for b in buildings_resp.json()]

            modules_resp = await client.get(
                f"{settings.supabase_url.rstrip('/')}/rest/v1/client_feature_modules",
                headers=svc_headers,
                params={
                    "account_id": f"eq.{user_id}",
                    "enabled": "eq.true",
                    "select": "module_slug,building_id",
                },
            )
            enabled: Set[str] = set(DEFAULT_MODULES)
            if modules_resp.status_code == 200:
                rows = modules_resp.json()
                if rows:
                    enabled = {r["module_slug"] for r in rows if r.get("enabled", True)}

            account_mode = profile.get("account_mode", "live")
            access_level = profile.get("access_level", "read_write")

            return UserContext(
                user_id=user_id,
                email=email,
                account_mode=account_mode,
                access_level=access_level,
                roles=roles,
                building_ids=building_ids,
                enabled_modules=enabled,
                authenticated=True,
            )
    except Exception as exc:
        logger.warning("fetch_user_context failed: %s", exc)
        return None


async def list_all_clients() -> List[Dict[str, Any]]:
    settings = get_settings()
    svc_key = settings.supabase_service_key or settings.supabase_key
    if not settings.supabase_url or not svc_key:
        return []

    headers = {"apikey": svc_key, "Authorization": f"Bearer {svc_key}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/profiles",
            headers=headers,
            params={"select": "user_id,email,display_name,account_mode,access_level,account_status,organization,created_at"},
        )
        if resp.status_code != 200:
            return []
        return resp.json()
