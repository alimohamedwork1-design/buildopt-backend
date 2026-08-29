from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps.auth import UserContext
from app.deps.guards import assert_building_access, empty_no_building, require_module_enabled, require_savings_verify
from app.services.savings_engine import SavingsOpportunity, SavingsState, get_opportunity, list_opportunities, transition_savings
from app.services.savings_mv_engine import verify_savings

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


@router.get("/opportunities/{opp_id}", response_model=SavingsOpportunity)
async def get_opportunity_detail(
    opp_id: str,
    user: UserContext = Depends(require_module_enabled("energy")),
):
    opp = get_opportunity(opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Savings opportunity not found")
    assert_building_access(user, opp.building_id)
    return opp


@router.post("/opportunities/{opp_id}/verify", response_model=SavingsOpportunity)
async def verify_opportunity(
    opp_id: str,
    body: dict,
    user: UserContext = Depends(require_savings_verify),
):
    opp = get_opportunity(opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Savings opportunity not found")
    assert_building_access(user, opp.building_id)
    actual_kwh = body.get("actual_kwh")
    if actual_kwh is None:
        raise HTTPException(status_code=400, detail="actual_kwh required")
    measurement_days = int(body.get("measurement_days", 0))
    return verify_savings(opp_id, actual_kwh=float(actual_kwh), measurement_days=measurement_days)


@router.post("/opportunities/{opp_id}/transition", response_model=SavingsOpportunity)
async def transition_opportunity(
    opp_id: str,
    body: dict,
    user: UserContext = Depends(require_savings_verify),
):
    opp = get_opportunity(opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Savings opportunity not found")
    assert_building_access(user, opp.building_id)
    new_state = body.get("state")
    if not new_state:
        raise HTTPException(status_code=400, detail="state required")
    if new_state == "VERIFIED" and opp.state != SavingsState.MONITORING:
        raise HTTPException(status_code=400, detail="VERIFIED requires MONITORING state with measurement data")
    try:
        return transition_savings(
            opp_id,
            SavingsState(new_state),
            actor_user_id=user.user_id,
            comment=body.get("comment"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
