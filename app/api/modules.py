from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.data.modules_registry import list_modules
from app.services.module_data_service import get_module_data

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
) -> Dict[str, Any]:
    normalized = "" if slug in ("overview", "home", "index") else slug
    return await get_module_data(normalized, building_id)


@router.get("/categories")
async def module_categories() -> Dict[str, Any]:
    from app.data.modules_registry import MODULE_CATEGORIES

    return {
        "categories": list(MODULE_CATEGORIES.keys()),
        "total_routes": len(list_modules()),
    }
