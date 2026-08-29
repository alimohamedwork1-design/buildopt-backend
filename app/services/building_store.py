from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings
from app.services.connection_store import _decrypt_password, _encrypt_password

logger = logging.getLogger("buildopt.buildings")

# In-memory fallback when Supabase tables are not migrated yet
_MEMORY_BUILDINGS: Dict[str, Dict[str, Any]] = {}
_MEMORY_CONNECTIONS: Dict[str, Dict[str, Any]] = {}
_MEMORY_POINTS: Dict[str, List[Dict[str, Any]]] = {}


def _svc_headers() -> Dict[str, str]:
    settings = get_settings()
    key = settings.supabase_service_key or settings.supabase_key
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation"}


def _base_url() -> str:
    return get_settings().supabase_url.rstrip("/")


async def create_building(owner_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    building_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": building_id,
        "owner_id": owner_id,
        "name": payload["name"],
        "address": payload.get("address"),
        "city": payload.get("city"),
        "country": payload.get("country", "UAE"),
        "latitude": payload.get("location", {}).get("lat") if isinstance(payload.get("location"), dict) else payload.get("latitude"),
        "longitude": payload.get("location", {}).get("lng") if isinstance(payload.get("location"), dict) else payload.get("longitude"),
        "building_type": payload.get("building_type"),
        "total_area_sqm": payload.get("total_area_sqm"),
        "floors": payload.get("floors"),
        "year_built": payload.get("year_built"),
        "bms_vendor": payload.get("bms_vendor"),
        "protocol": payload.get("protocol"),
        "connection_status": "disconnected",
        "systems": payload.get("systems") or [],
        "site_profile": payload.get("site_profile", "building_only"),
        "created_at": now,
        "updated_at": now,
    }

    creds = payload.get("connection_credentials")
    if creds and isinstance(creds, dict):
        await save_connection(building_id, creds, test=False)

    settings = get_settings()
    if not settings.supabase_url:
        _MEMORY_BUILDINGS[building_id] = row
        return row

    headers = _svc_headers()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{_base_url()}/rest/v1/buildings", headers=headers, json={
            k: v for k, v in row.items() if k not in ("created_at",) or True
        })
        if resp.status_code in (200, 201):
            data = resp.json()
            return data[0] if isinstance(data, list) else data
        logger.warning("Supabase building create %s: %s", resp.status_code, resp.text[:200])
        _MEMORY_BUILDINGS[building_id] = row
        return row


async def list_buildings_for_owner(owner_id: str) -> List[Dict[str, Any]]:
    settings = get_settings()
    if not settings.supabase_url:
        return [b for b in _MEMORY_BUILDINGS.values() if b.get("owner_id") == owner_id]

    headers = _svc_headers()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{_base_url()}/rest/v1/buildings",
            headers=headers,
            params={"owner_id": f"eq.{owner_id}", "select": "*", "order": "created_at.desc"},
        )
        if resp.status_code == 200:
            return resp.json()
        return [b for b in _MEMORY_BUILDINGS.values() if b.get("owner_id") == owner_id]


async def get_building(building_id: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    settings = get_settings()
    if not settings.supabase_url:
        row = _MEMORY_BUILDINGS.get(building_id)
        if row and owner_id and row.get("owner_id") != owner_id:
            return None
        return row

    headers = _svc_headers()
    params: Dict[str, str] = {"id": f"eq.{building_id}", "select": "*"}
    if owner_id:
        params["owner_id"] = f"eq.{owner_id}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{_base_url()}/rest/v1/buildings", headers=headers, params=params)
        if resp.status_code == 200 and resp.json():
            return resp.json()[0]
    return _MEMORY_BUILDINGS.get(building_id)


async def save_connection(building_id: str, creds: Dict[str, Any], *, test: bool = False) -> Dict[str, Any]:
    settings = get_settings()
    encrypted = _encrypt_password(str(creds.get("password", "")), settings.secret_key) if creds.get("password") else None
    conn = {
        "building_id": building_id,
        "host": creds.get("host"),
        "username": creds.get("username"),
        "password_encrypted": encrypted,
        "protocol_version": creds.get("version", "v4"),
        "extra": {k: v for k, v in creds.items() if k not in ("host", "username", "password", "version")},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _MEMORY_CONNECTIONS[building_id] = conn

    if settings.supabase_url:
        headers = _svc_headers()
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{_base_url()}/rest/v1/building_connections",
                headers={**headers, "Prefer": "resolution=merge-duplicates"},
                json=conn,
                params={"on_conflict": "building_id"},
            )
    return conn


async def get_connection(building_id: str) -> Optional[Dict[str, Any]]:
    settings = get_settings()
    if settings.supabase_url:
        headers = _svc_headers()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_base_url()}/rest/v1/building_connections",
                headers=headers,
                params={"building_id": f"eq.{building_id}", "select": "*"},
            )
            if resp.status_code == 200 and resp.json():
                row = resp.json()[0]
                pwd = _decrypt_password(row.get("password_encrypted", ""), settings.secret_key)
                row["password"] = pwd
                return row
    conn = _MEMORY_CONNECTIONS.get(building_id)
    if conn and conn.get("password_encrypted"):
        conn = dict(conn)
        conn["password"] = _decrypt_password(conn["password_encrypted"], settings.secret_key)
    return conn


async def update_connection_status(building_id: str, status: str) -> None:
    _MEMORY_BUILDINGS.get(building_id, {}).update({"connection_status": status})
    settings = get_settings()
    if settings.supabase_url:
        headers = _svc_headers()
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.patch(
                f"{_base_url()}/rest/v1/buildings",
                headers=headers,
                params={"id": f"eq.{building_id}"},
                json={"connection_status": status, "updated_at": datetime.now(timezone.utc).isoformat()},
            )


async def update_site_profile(building_id: str, site_profile: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    valid = {"building_only", "building_with_industrial_cooling", "industrial_cooling_only"}
    if site_profile not in valid:
        raise ValueError(f"Invalid site_profile: {site_profile}")

    now = datetime.now(timezone.utc).isoformat()
    mem = _MEMORY_BUILDINGS.get(building_id)
    if mem:
        if owner_id and mem.get("owner_id") != owner_id:
            return None
        mem["site_profile"] = site_profile
        mem["updated_at"] = now
        return mem

    settings = get_settings()
    if not settings.supabase_url:
        return None

    headers = _svc_headers()
    params: Dict[str, str] = {"id": f"eq.{building_id}"}
    if owner_id:
        params["owner_id"] = f"eq.{owner_id}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.patch(
            f"{_base_url()}/rest/v1/buildings",
            headers={**headers, "Prefer": "return=representation"},
            params=params,
            json={"site_profile": site_profile, "updated_at": now},
        )
        if resp.status_code in (200, 204) and resp.text.strip():
            data = resp.json()
            return data[0] if isinstance(data, list) else data
        if resp.status_code in (200, 204):
            return await get_building(building_id, owner_id=owner_id)
    return None


async def save_points(building_id: str, points: List[Dict[str, Any]]) -> int:
    _MEMORY_POINTS[building_id] = points
    settings = get_settings()
    if not settings.supabase_url:
        return len(points)

    headers = _svc_headers()
    rows = [{**p, "building_id": building_id} for p in points]
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(f"{_base_url()}/rest/v1/building_points", headers=headers, json=rows)
        if resp.status_code in (200, 201):
            return len(rows)
    return len(points)


async def get_modules_for_account(account_id: str, building_id: Optional[str] = None) -> List[Dict[str, Any]]:
    settings = get_settings()
    if not settings.supabase_url:
        from app.services.account_service import DEFAULT_MODULES
        return [{"module_slug": s, "enabled": True, "building_id": building_id} for s in DEFAULT_MODULES]

    headers = _svc_headers()
    params: Dict[str, str] = {"account_id": f"eq.{account_id}", "select": "module_slug,enabled,building_id"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{_base_url()}/rest/v1/client_feature_modules", headers=headers, params=params)
        if resp.status_code == 200:
            return resp.json()
    return []


async def set_modules_for_account(account_id: str, modules: List[Dict[str, Any]], updated_by: str) -> List[Dict[str, Any]]:
    settings = get_settings()
    results = []
    if not settings.supabase_url:
        return modules

    headers = _svc_headers()
    async with httpx.AsyncClient(timeout=15.0) as client:
        for mod in modules:
            row = {
                "account_id": account_id,
                "building_id": mod.get("building_id"),
                "module_slug": mod["module_slug"],
                "enabled": mod.get("enabled", True),
                "updated_by": updated_by,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            resp = await client.post(
                f"{_base_url()}/rest/v1/client_feature_modules",
                headers={**headers, "Prefer": "resolution=merge-duplicates"},
                json=row,
                params={"on_conflict": "account_id,building_id,module_slug"},
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                results.append(data[0] if isinstance(data, list) else data)
    return results


async def set_access_level(account_id: str, access_level: str) -> bool:
    settings = get_settings()
    if not settings.supabase_url:
        return True
    headers = _svc_headers()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.patch(
            f"{_base_url()}/rest/v1/profiles",
            headers=headers,
            params={"user_id": f"eq.{account_id}"},
            json={"access_level": access_level},
        )
        return resp.status_code in (200, 204)
