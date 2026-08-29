from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.data.modules_registry import list_modules
from app.deps.auth import UserContext, get_optional_user
from app.deps.guards import assert_building_access, empty_no_building
from app.services.module_data_service import get_module_data
from pydantic import BaseModel

router = APIRouter(prefix="/modules", tags=["modules"])


class ModuleListItem(BaseModel):
    slug: str
    path: str
    category: str
    api_endpoint: str


@router.get("", response_model=List[ModuleListItem])
async def list_all_modules() -> List[ModuleListItem]:
    return [ModuleListItem(**m) for m in list_modules()]


@router.get("/{slug}/data")
async def module_data(
    slug: str,
    building_id: str = Query(default="burj-khalifa-01"),
    user: UserContext = Depends(get_optional_user),
) -> Dict[str, Any]:
    from app.utils.arabic_utils import bilingual_error

    mod_slug = slug.replace("-", "_")
    enabled = user.enabled_modules
    module_allowed = (
        mod_slug in enabled
        or slug in enabled
        or slug.replace("_", "-") in enabled
    )
    if user.is_live_account:
        if not user.authenticated:
            raise HTTPException(status_code=401, detail=bilingual_error("Authentication required", "المصادقة مطلوبة"))
        if not user.has_buildings:
            raise HTTPException(status_code=404, detail=empty_no_building())
        if not module_allowed and not user.is_admin:
            raise HTTPException(status_code=403, detail=bilingual_error(f"Module '{slug}' disabled", "الوحدة معطلة"))
    assert_building_access(user, building_id)
    normalized = "" if slug in ("overview", "home", "index") else slug
    return await get_module_data(normalized, building_id, user=user)


@router.get("/categories")
async def module_categories() -> Dict[str, Any]:
    from app.data.modules_registry import MODULE_CATEGORIES

    return {
        "categories": list(MODULE_CATEGORIES.keys()),
        "total_routes": len(list_modules()),
    }
