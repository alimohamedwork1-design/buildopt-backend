from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.data.modules_registry import list_modules
from app.deps.auth import UserContext
from app.deps.guards import require_admin
from app.models.schemas import AccessLevelUpdate, ModuleToggle
from app.services import live_data_service
from app.services.account_service import list_all_clients
from app.services.building_store import (
    get_building,
    get_modules_for_account,
    list_buildings_for_owner,
    set_access_level,
    set_modules_for_account,
)
from app.services.edge_heartbeat_store import edge_heartbeat_store
from app.utils.arabic_utils import bilingual_error

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/clients")
async def admin_list_clients(admin: UserContext = Depends(require_admin)) -> List[Dict[str, Any]]:
    return await list_all_clients()


@router.get("/control-plane")
async def admin_control_plane(admin: UserContext = Depends(require_admin)) -> Dict[str, Any]:
    """Safe platform overview for Admin OS — no credentials or secret material."""
    clients = await list_all_clients()
    building_total = 0
    connected_buildings = 0
    client_rows: List[Dict[str, Any]] = []

    for client in clients[:100]:
        client_id = str(client.get("user_id") or "")
        buildings = await list_buildings_for_owner(client_id) if client_id else []
        building_total += len(buildings)
        connected = sum(1 for b in buildings if b.get("connection_status") == "connected")
        connected_buildings += connected
        client_rows.append(
            {
                "user_id": client_id,
                "email": client.get("email"),
                "display_name": client.get("display_name"),
                "organization": client.get("organization"),
                "account_mode": client.get("account_mode", "live"),
                "access_level": client.get("access_level", "read_write"),
                "account_status": client.get("account_status", "active"),
                "buildings": len(buildings),
                "connected_buildings": connected,
            }
        )

    maturity = Counter(str(m.get("maturity") or "unknown") for m in list_modules())
    gateway_states = Counter(str(g.get("state") or "UNKNOWN") for g in edge_heartbeat_store.list_gateways())
    account_modes = Counter(str(c.get("account_mode") or "live") for c in clients)
    access_levels = Counter(str(c.get("access_level") or "read_write") for c in clients)
    statuses = Counter(str(c.get("account_status") or "active") for c in clients)

    return {
        "platform": {
            "clients": len(clients),
            "buildings": building_total,
            "connected_buildings": connected_buildings,
            "gateways": sum(gateway_states.values()),
        },
        "account_modes": dict(account_modes),
        "access_levels": dict(access_levels),
        "account_statuses": dict(statuses),
        "gateway_states": dict(gateway_states),
        "module_maturity": dict(maturity),
        "clients": client_rows,
        "guardrails": {
            "automatic_writeback": False,
            "shadow_optimization": True,
            "human_approval_required": True,
            "live_demo_fallback": False,
        },
        "available_controls": [
            "client_modules",
            "client_access_level",
            "user_roles",
            "building_connections",
            "gateway_tokens",
            "semantic_mapping",
            "audit_review",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/clients/{client_id}/buildings")
async def admin_client_buildings(client_id: str, admin: UserContext = Depends(require_admin)) -> List[Dict[str, Any]]:
    return await list_buildings_for_owner(client_id)


@router.get("/clients/{client_id}/buildings/{building_id}/data")
async def admin_client_building_data(
    client_id: str,
    building_id: str,
    admin: UserContext = Depends(require_admin),
) -> Dict[str, Any]:
    row = await get_building(building_id, client_id)
    if not row:
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))

    # Explicit live tenant context prevents global demo settings from contaminating
    # admin inspection of a real client's building.
    tenant_context = UserContext(
        user_id=client_id,
        account_mode="live",
        access_level="read_only",
        roles=["admin"],
        building_ids=[building_id],
        authenticated=True,
    )
    live = await live_data_service.get_live_data(building_id, user=tenant_context)
    metrics = live_data_service.get_building_metrics(building_id, "24h", user=tenant_context)
    return {
        "building": row,
        "live": live.model_dump(mode="json") if live else None,
        "metrics": metrics.model_dump(mode="json") if metrics else None,
        "account_mode": "live",
        "demo_fallback_allowed": False,
    }


@router.get("/clients/{client_id}/modules")
async def admin_get_modules(client_id: str, admin: UserContext = Depends(require_admin)) -> List[Dict[str, Any]]:
    return await get_modules_for_account(client_id)


@router.put("/clients/{client_id}/modules")
async def admin_set_modules(
    client_id: str,
    modules: List[ModuleToggle],
    admin: UserContext = Depends(require_admin),
) -> List[Dict[str, Any]]:
    payload = [m.model_dump() for m in modules]
    return await set_modules_for_account(client_id, payload, admin.user_id or "")


@router.put("/clients/{client_id}/access-level")
async def admin_set_access_level(
    client_id: str,
    body: AccessLevelUpdate,
    admin: UserContext = Depends(require_admin),
) -> Dict[str, Any]:
    ok = await set_access_level(client_id, body.access_level)
    if not ok:
        raise HTTPException(status_code=503, detail=bilingual_error("Could not update access level", "تعذر تحديث مستوى الوصول"))
    return {"account_id": client_id, "access_level": body.access_level}
