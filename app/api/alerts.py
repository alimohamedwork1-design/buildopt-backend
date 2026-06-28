from typing import List

from fastapi import APIRouter, HTTPException

from app.models.schemas import Alert, AlertAcknowledge, FDDResult
from app.services import demo_mode
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=List[Alert])
async def list_alerts() -> List[Alert]:
    return demo_mode.list_alerts()


@router.get("/history", response_model=List[Alert])
async def alert_history() -> List[Alert]:
    return demo_mode.list_alert_history()


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, payload: AlertAcknowledge) -> dict:
    alerts = demo_mode.list_alerts()
    if not any(alert.id == alert_id for alert in alerts):
        raise HTTPException(status_code=404, detail=bilingual_error("Alert not found", "التنبيه غير موجود"))

    return {
        "success": True,
        "alert_id": alert_id,
        "acknowledged_by": payload.acknowledged_by,
        "message": bilingual_success("Alert acknowledged", "تم تأكيد التنبيه"),
    }


@router.get("/fdd", response_model=List[FDDResult])
async def fdd_results() -> List[FDDResult]:
    return demo_mode.list_fdd_results()
