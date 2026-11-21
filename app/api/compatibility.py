"""Read-only, manufacturer-neutral assessment endpoints.

Protocol catalog is public; site-specific assessments always require a
verified account identity and explicit building access.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.deps.auth import get_required_user
from app.models.user_context import UserContext
from app.services.compatibility_service import (
    SiteAssessment,
    TwinReadinessRequest,
    assess_site,
    get_compatibility_matrix,
    twin_readiness,
)

router = APIRouter(prefix="/compatibility", tags=["compatibility"])


def require_assigned_building(user: UserContext, building_id: str) -> None:
    # Stronger than general demo allowance: never assess a real site without
    # an explicitly assigned building even in an account configured for demo.
    if not user.authenticated:
        raise HTTPException(status_code=401, detail="Authentication required")
    if building_id not in user.building_ids and not user.is_admin:
        raise HTTPException(status_code=403, detail="Building not assigned to this account")


@router.get("/matrix")
async def protocol_matrix() -> dict:
    return {
        "protocols": get_compatibility_matrix(),
        "disclaimer": "Protocol code is not proof of a validated connection to any site.",
    }


@router.post("/assess")
async def assess_site_readiness(
    body: SiteAssessment,
    user: UserContext = Depends(get_required_user),
) -> dict:
    require_assigned_building(user, body.building_id)
    # No input data is persisted. Only a signed engineering review can
    # advance a production integration to field-validated.
    return assess_site(body)


@router.post("/twin-readiness")
async def assess_twin_readiness(
    body: TwinReadinessRequest,
    user: UserContext = Depends(get_required_user),
) -> dict:
    require_assigned_building(user, body.building_id)
    try:
        return twin_readiness(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
