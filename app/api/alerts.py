from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.deps.auth import UserContext, get_optional_user
from app.deps.guards import empty_no_building, require_module_enabled, require_write_access
from app.models.schemas import Alert, AlertAcknowledge
from app.services import live_data_service
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=List[Alert])
async def list_alerts(user: UserContext = Depends(require_module_enabled("alerts"))) -> List[Alert]:
    if user.is_live_account and not user.has_buildings:
        return []
    return live_data_service.list_alerts(user=user)


@router.get("/history", response_model=List[Alert])
async def alert_history(user: UserContext = Depends(require_module_enabled("alerts"))) -> List[Alert]:
    if user.is_live_account and not user.has_buildings:
        return []
    return live_data_service.list_alert_history(user=user)


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    payload: AlertAcknowledge,
    user: UserContext = Depends(require_write_access),
) -> dict:
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    ok = live_data_service.acknowledge_alert(alert_id, payload.acknowledged_by)
    if not ok:
        raise HTTPException(status_code=404, detail=bilingual_error("Alert not found", "التنبيه غير موجود"))

    return {
        "success": True,
        "alert_id": alert_id,
        "acknowledged_by": payload.acknowledged_by,
        "message": bilingual_success("Alert acknowledged", "تم تأكيد التنبيه"),
    }


@router.get("/fdd")
async def fdd_results(user: UserContext = Depends(require_module_enabled("fdd"))):
    if user.is_live_account and not user.has_buildings:
        return []
    return live_data_service.list_fdd_results(user=user)
