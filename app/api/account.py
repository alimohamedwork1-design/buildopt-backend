from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from app.deps.auth import UserContext, get_required_user
from app.services.building_store import get_modules_for_account

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/me")
async def get_account_profile(user: UserContext = Depends(get_required_user)) -> Dict[str, Any]:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "account_mode": user.account_mode,
        "access_level": user.access_level,
        "roles": user.roles,
        "building_ids": user.building_ids,
        "has_buildings": user.has_buildings,
        "is_admin": user.is_admin,
    }


@router.get("/modules")
async def get_my_modules(user: UserContext = Depends(get_required_user)) -> List[Dict[str, Any]]:
    modules = await get_modules_for_account(user.user_id or "")
    return modules or [{"module_slug": s, "enabled": True} for s in sorted(user.enabled_modules)]
