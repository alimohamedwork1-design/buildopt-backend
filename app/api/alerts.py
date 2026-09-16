from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps.auth import UserContext
from app.deps.guards import empty_no_building, require_admin, require_module_enabled, require_write_access
from app.models.schemas import Alert, AlertAcknowledge
from app.services import live_data_service
from app.services.notification_service import SUPPORTED_CHANNELS, channel_status, send_notification
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/alerts", tags=["alerts"])


class NotificationTestRequest(BaseModel):
    channel: str
    title: str = Field(default="BuildOpt test notification", max_length=120)
    message: str = Field(default="BuildOpt notification channel test", max_length=1000)


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


@router.get("/notifications/channels")
async def notification_channels(
    user: UserContext = Depends(require_module_enabled("alerts")),
) -> dict:
    status = channel_status()
    status["state"] = "CONFIGURED" if status["configured_channels"] else "NOT_CONFIGURED"
    status["test_delivery_requires_admin"] = True
    return status


@router.post("/notifications/test")
async def test_notification_channel(
    body: NotificationTestRequest,
    admin: UserContext = Depends(require_admin),
) -> dict:
    if body.channel not in SUPPORTED_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail=bilingual_error("Unsupported notification channel", "قناة الإشعار غير مدعومة"),
        )
    result = await send_notification(body.channel, body.message, title=body.title)
    if result["state"] == "NOT_CONFIGURED":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NOT_CONFIGURED",
                "channel": body.channel,
                "message": bilingual_error(
                    "Notification provider is not configured",
                    "موفر الإشعارات غير مُعد",
                ),
            },
        )
    if not result["sent"]:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "DELIVERY_FAILED",
                "channel": body.channel,
                "message": bilingual_error("Notification delivery failed", "فشل إرسال الإشعار"),
            },
        )
    return {
        "channel": body.channel,
        "sent": True,
        "state": "SENT",
        "message": bilingual_success("Test notification sent", "تم إرسال إشعار الاختبار"),
    }


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
