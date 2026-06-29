from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import Alert, AlertAcknowledge, EquipmentDetail, EquipmentSummary, MetricPoint, SetpointUpdate
from app.services import live_data_service
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=List[Alert])
async def list_alerts() -> List[Alert]:
    return live_data_service.list_alerts()


@router.get("/history", response_model=List[Alert])
async def alert_history() -> List[Alert]:
    return live_data_service.list_alert_history()


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, payload: AlertAcknowledge) -> dict:
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
async def fdd_results():
    return live_data_service.list_fdd_results()
