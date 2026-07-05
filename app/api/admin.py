from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.deps.auth import UserContext
from app.deps.guards import require_admin, require_write_access
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
from app.utils.arabic_utils import bilingual_error

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/clients")
async def admin_list_clients(admin: UserContext = Depends(require_admin)) -> List[Dict[str, Any]]:
    return await list_all_clients()


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
    live = await live_data_service.get_live_data(building_id)
    metrics = live_data_service.get_building_metrics(building_id, "24h")
    return {"building": row, "live": live.model_dump(mode="json") if live else None, "metrics": metrics.model_dump(mode="json") if metrics else None}


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
