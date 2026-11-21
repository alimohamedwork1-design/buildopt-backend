"""Authenticated, bounded, read-only engineering evidence interpretation."""
from fastapi import APIRouter, Depends
from app.api.compatibility import require_assigned_building
from app.deps.auth import get_required_user
from app.models.user_context import UserContext
from app.services.evidence_copilot import InvestigationRequest, analyze_evidence

router = APIRouter(prefix="/engineering-copilot", tags=["engineering-copilot"])

@router.post("/investigate")
async def investigate(
    body: InvestigationRequest,
    user: UserContext = Depends(get_required_user),
) -> dict:
    require_assigned_building(user, body.building_id)
    # This computes an ephemeral analysis of the caller-supplied approved points.
    # No BMS connection, model invocation, command or persistence.
    return analyze_evidence(body)
