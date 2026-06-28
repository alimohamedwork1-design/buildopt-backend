import asyncio
import json
from typing import AsyncGenerator, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    BilingualMessage,
    BuildingDetail,
    BuildingMetrics,
    BuildingSummary,
    ControlCommand,
    ControlResponse,
    LiveBuildingData,
)
from app.services import live_data_service
from app.utils.arabic_utils import bilingual_error

router = APIRouter(prefix="/buildings", tags=["buildings"])


@router.get("", response_model=List[BuildingSummary])
async def list_buildings() -> List[BuildingSummary]:
    return live_data_service.list_buildings()


@router.get("/{building_id}", response_model=BuildingDetail)
async def get_building(building_id: str) -> BuildingDetail:
    building = live_data_service.get_building(building_id)
    if not building:
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))
    return building


@router.get("/{building_id}/live", response_model=LiveBuildingData)
async def get_live_data(building_id: str) -> LiveBuildingData:
    data = await live_data_service.get_live_data(building_id)
    if not data:
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))
    return data


@router.get("/{building_id}/live/stream")
async def stream_live_data(building_id: str) -> StreamingResponse:
    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            data = await live_data_service.get_live_data(building_id)
            if data:
                payload = data.model_dump(mode="json")
                yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{building_id}/metrics", response_model=BuildingMetrics)
async def get_metrics(
    building_id: str,
    period: str = Query(default="24h", pattern="^(1h|24h|7d)$"),
) -> BuildingMetrics:
    metrics = live_data_service.get_building_metrics(building_id, period)
    if not metrics:
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))
    return metrics


@router.post("/{building_id}/control", response_model=ControlResponse)
async def send_control(building_id: str, command: ControlCommand) -> ControlResponse:
    building = live_data_service.get_building(building_id)
    if not building:
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))

    return ControlResponse(
        success=True,
        message=BilingualMessage(
            en=f"Command '{command.command}' accepted for {command.target}",
            ar=f"تم قبول الأمر '{command.command}' للهدف {command.target}",
        ),
        building_id=building_id,
        command=command.command,
    )
