from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import EquipmentDetail, EquipmentSummary, MetricPoint, SetpointUpdate
from app.services import live_data_service
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/equipment", tags=["equipment"])


@router.get("", response_model=List[EquipmentSummary])
async def list_equipment(building_id: Optional[str] = Query(default=None)) -> List[EquipmentSummary]:
    return live_data_service.list_equipment(building_id)


@router.get("/{equipment_id}", response_model=EquipmentDetail)
async def get_equipment(equipment_id: str) -> EquipmentDetail:
    equipment = live_data_service.get_equipment(equipment_id)
    if not equipment:
        raise HTTPException(status_code=404, detail=bilingual_error("Equipment not found", "المعدة غير موجودة"))
    return equipment


@router.get("/{equipment_id}/history", response_model=List[MetricPoint])
async def get_equipment_history(equipment_id: str) -> List[MetricPoint]:
    history = live_data_service.get_equipment_history(equipment_id)
    if not history:
        raise HTTPException(status_code=404, detail=bilingual_error("Equipment not found", "المعدة غير موجودة"))
    return history


@router.post("/{equipment_id}/setpoint")
async def update_setpoint(equipment_id: str, update: SetpointUpdate) -> dict:
    equipment = live_data_service.get_equipment(equipment_id)
    if not equipment:
        raise HTTPException(status_code=404, detail=bilingual_error("Equipment not found", "المعدة غير موجودة"))

    return {
        "success": True,
        "equipment_id": equipment_id,
        "setpoint": update.setpoint,
        "message": bilingual_success(
            f"Setpoint updated to {update.setpoint}",
            f"تم تحديث نقطة الضبط إلى {update.setpoint}",
        ),
    }
