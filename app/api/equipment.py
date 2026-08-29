from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps.auth import UserContext
from app.deps.guards import assert_building_access, empty_no_building, require_module_enabled, require_write_access
from app.models.schemas import EquipmentDetail, EquipmentSummary, MetricPoint, SetpointUpdate
from app.models.errors import ErrorCode, api_error
from app.services import live_data_service
from app.services.audit_log import record_audit
from app.services.write_policy import DEFAULT_WRITE_MODE, validate_write_request
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/equipment", tags=["equipment"])


@router.get("", response_model=List[EquipmentSummary])
async def list_equipment(
    building_id: Optional[str] = Query(default=None),
    user: UserContext = Depends(require_module_enabled("equipment")),
) -> List[EquipmentSummary]:
    if user.is_live_account and not user.has_buildings:
        return []
    if building_id:
        assert_building_access(user, building_id)
    return live_data_service.list_equipment(building_id, user=user)


@router.get("/{equipment_id}", response_model=EquipmentDetail)
async def get_equipment(
    equipment_id: str,
    user: UserContext = Depends(require_module_enabled("equipment")),
) -> EquipmentDetail:
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    equipment = live_data_service.get_equipment(equipment_id, user=user)
    if not equipment:
        raise HTTPException(status_code=404, detail=bilingual_error("Equipment not found", "المعدة غير موجودة"))
    return equipment


@router.get("/{equipment_id}/history", response_model=List[MetricPoint])
async def get_equipment_history(
    equipment_id: str,
    user: UserContext = Depends(require_module_enabled("equipment")),
) -> List[MetricPoint]:
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    history = live_data_service.get_equipment_history(equipment_id, user=user)
    if not history:
        raise HTTPException(status_code=404, detail=bilingual_error("Equipment not found", "المعدة غير موجودة"))
    return history


@router.post("/{equipment_id}/setpoint")
async def update_setpoint(
    equipment_id: str,
    update: SetpointUpdate,
    user: UserContext = Depends(require_write_access),
) -> dict:
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    equipment = live_data_service.get_equipment(equipment_id, user=user)
    if not equipment:
        raise HTTPException(status_code=404, detail=bilingual_error("Equipment not found", "المعدة غير موجودة"))

    validate_write_request(user, mode=DEFAULT_WRITE_MODE, requested_value=update.setpoint)
    record_audit(
        actor=user.user_id,
        tenant=user.user_id,
        action="equipment.setpoint.request",
        resource=equipment_id,
        result="blocked_read_only",
        metadata={"setpoint": update.setpoint},
    )
    raise api_error(
        ErrorCode.COMMAND_NOT_ALLOWED,
        "Write-back is disabled by default (READ_ONLY mode)",
        "الكتابة معطلة افتراضياً (وضع القراءة فقط)",
        status_code=403,
    )
