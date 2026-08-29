from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps.auth import UserContext
from app.deps.guards import assert_building_access, empty_no_building, require_module_enabled
from app.services.savings_engine import SavingsOpportunity, list_opportunities

router = APIRouter(prefix="/savings", tags=["savings"])


@router.get("/opportunities", response_model=List[SavingsOpportunity])
async def get_opportunities(
    building_id: Optional[str] = Query(default=None),
    user: UserContext = Depends(require_module_enabled("energy")),
):
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    if building_id:
        assert_building_access(user, building_id)
    return list_opportunities(building_id)
