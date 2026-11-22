"""Read-only, account/building-authorized engineering acceptance reviews."""
from fastapi import APIRouter, Depends
from app.deps.auth import get_required_user
from app.models.user_context import UserContext
from app.api.compatibility import require_assigned_building
from app.services.engineering_acceptance import (
    PortfolioReviewRequest, TwinCalibrationRequest, OnPremPreflightRequest,
    review_portfolio, review_twin_calibration, review_onprem,
)

router=APIRouter(prefix="/delivery-review",tags=["delivery-review"])


@router.post("/portfolio")
async def portfolio_comparison(
    payload:PortfolioReviewRequest,user:UserContext=Depends(get_required_user)
)->dict:
    require_assigned_building(user,payload.building_id)
    # Never allow an authorized site to cross-reference an unauthorized
    # customer's building merely by submitting its name inside the payload.
    for site in payload.sites:
        require_assigned_building(user,site.building_id)
    return review_portfolio(payload)


@router.post("/twin-calibration")
async def twin_calibration(
    payload:TwinCalibrationRequest,user:UserContext=Depends(get_required_user)
)->dict:
    require_assigned_building(user,payload.building_id)
    return review_twin_calibration(payload)


@router.post("/onprem")
async def onprem_preflight(
    payload:OnPremPreflightRequest,user:UserContext=Depends(get_required_user)
)->dict:
    require_assigned_building(user,payload.building_id)
    return review_onprem(payload)
