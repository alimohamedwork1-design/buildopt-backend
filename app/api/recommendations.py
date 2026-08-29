from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps.auth import UserContext
from app.deps.guards import (
    assert_building_access,
    empty_no_building,
    require_module_enabled,
    require_recommendation_write,
)
from app.services.recommendations_store import (
    Recommendation,
    RecommendationState,
    get_recommendation,
    list_recommendations,
    transition_recommendation,
)

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


@router.get("/{rec_id}", response_model=Recommendation)
async def get_recommendation_detail(
    rec_id: str,
    user: UserContext = Depends(require_module_enabled("fdd")),
):
    rec = get_recommendation(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    assert_building_access(user, rec.building_id)
    return rec


@router.post("/{rec_id}/approve", response_model=Recommendation)
async def approve_recommendation(
    rec_id: str,
    body: dict,
    user: UserContext = Depends(require_recommendation_write),
):
    rec = get_recommendation(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    assert_building_access(user, rec.building_id)
    try:
        return transition_recommendation(
            rec_id,
            RecommendationState.APPROVED,
            actor_user_id=user.user_id,
            comment=body.get("comment"),
            approved_by=user.email or user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{rec_id}/reject", response_model=Recommendation)
async def reject_recommendation(
    rec_id: str,
    body: dict,
    user: UserContext = Depends(require_recommendation_write),
):
    rec = get_recommendation(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    assert_building_access(user, rec.building_id)
    try:
        return transition_recommendation(
            rec_id,
            RecommendationState.REJECTED,
            actor_user_id=user.user_id,
            comment=body.get("comment"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{rec_id}/transition", response_model=Recommendation)
async def transition_recommendation_state(
    rec_id: str,
    body: dict,
    user: UserContext = Depends(require_recommendation_write),
):
    rec = get_recommendation(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    assert_building_access(user, rec.building_id)
    new_state = body.get("state")
    if not new_state:
        raise HTTPException(status_code=400, detail="state required")
    try:
        return transition_recommendation(
            rec_id,
            RecommendationState(new_state),
            actor_user_id=user.user_id,
            comment=body.get("comment"),
            approved_by=user.email if new_state == "APPROVED" else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
