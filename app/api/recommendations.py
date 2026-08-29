from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps.auth import UserContext
from app.deps.guards import assert_building_access, empty_no_building, require_module_enabled
from app.services.recommendations_store import Recommendation, list_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=List[Recommendation])
async def get_recommendations(
    building_id: Optional[str] = Query(default=None),
    user: UserContext = Depends(require_module_enabled("fdd")),
):
    if user.is_live_account and not user.has_buildings:
        return []
    if building_id:
        assert_building_access(user, building_id)
    return list_recommendations(building_id)
