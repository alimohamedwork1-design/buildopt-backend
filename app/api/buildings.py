from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.deps.auth import UserContext, get_optional_user, get_required_user
from app.deps.guards import assert_building_access, empty_no_building, require_write_access
from app.models.schemas import (
    BuildingCreateRequest,
    BuildingDetail,
    BuildingMetrics,
    BuildingSummary,
    ControlCommand,
    ControlResponse,
    LiveBuildingData,
    SiteProfileUpdate,
)
from app.services import live_data_service
from app.services.building_store import (
    create_building,
    get_building as get_building_row,
    get_connection,
    list_buildings_for_owner,
    save_connection,
    save_points,
    update_connection_status,
)
from app.services.excel_import import parse_building_excel
from app.services.jci_metasys import JCIMetasysClient
from app.services.site_profile_store import get_site_profile, set_site_profile
from app.utils.arabic_utils import bilingual_error, bilingual_success

router = APIRouter(prefix="/buildings", tags=["buildings"])


def _row_to_summary(row: Dict[str, Any]) -> BuildingSummary:
    loc_parts = [p for p in [row.get("address"), row.get("city"), row.get("country")] if p]
    return BuildingSummary(
        id=str(row["id"]),
        name=row["name"],
        location=", ".join(loc_parts) if loc_parts else row.get("city") or "—",
        floors=int(row.get("floors") or 0),
        area_sqm=float(row.get("total_area_sqm") or 0),
        status="online" if row.get("connection_status") == "connected" else "offline",
        energy_savings_pct=0.0,
        active_alerts=0,
        site_profile=row.get("site_profile") or "building_only",
    )


@router.get("", response_model=List[BuildingSummary])
async def list_buildings(user: UserContext = Depends(get_optional_user)) -> List[BuildingSummary]:
    if user.is_live_account:
        if not user.authenticated:
            raise HTTPException(status_code=401, detail=bilingual_error("Authentication required", "المصادقة مطلوبة"))
        rows = await list_buildings_for_owner(user.user_id or "")
        return [_row_to_summary(r) for r in rows]
    if user.allows_demo_data():
        return live_data_service.list_buildings()
    return []


@router.post("", status_code=201)
async def create_building_endpoint(
    body: BuildingCreateRequest,
    user: UserContext = Depends(require_write_access),
) -> Dict[str, Any]:
    payload = body.model_dump()
    if body.connection_credentials:
        payload["connection_credentials"] = body.connection_credentials.model_dump()
    row = await create_building(user.user_id or "", payload)
    return {"building": row, "message": bilingual_success("Building created", "تم إنشاء المبنى")}


@router.get("/{building_id}", response_model=BuildingDetail)
async def get_building(building_id: str, user: UserContext = Depends(get_optional_user)) -> BuildingDetail:
    assert_building_access(user, building_id)
    if user.is_live_account:
        row = await get_building_row(building_id, user.user_id)
        if not row:
            raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))
        summary = _row_to_summary(row)
        return BuildingDetail(
            **summary.model_dump(),
            bms_type=row.get("bms_vendor") or "—",
            installed_capacity_kw=0.0,
            last_updated=datetime.now(timezone.utc),
        )
    building = live_data_service.get_building(building_id)
    if not building:
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))
    return building


@router.get("/{building_id}/live", response_model=LiveBuildingData)
async def get_live_data(building_id: str, user: UserContext = Depends(get_optional_user)) -> LiveBuildingData:
    assert_building_access(user, building_id)
    if user.is_live_account:
        row = await get_building_row(building_id, user.user_id)
        if not row:
            raise HTTPException(status_code=404, detail=empty_no_building())
        if row.get("connection_status") != "connected":
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "NOT_CONFIGURED",
                    "empty_state": True,
                    "reason": "bms_not_connected",
                    "message": bilingual_error(
                        "Building registered but BMS not connected yet. Run test-connection first.",
                        "المبنى مسجل لكن BMS غير متصل. نفّذ test-connection أولاً.",
                    ),
                },
            )
    data = await live_data_service.get_live_data(building_id, user=user)
    if not data:
        if user.is_live_account:
            raise HTTPException(
                status_code=503,
                detail=bilingual_error("Live data unavailable", "البيانات الحية غير متوفرة"),
            )
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))
    return data


@router.get("/{building_id}/live/stream")
async def stream_live_data(building_id: str, user: UserContext = Depends(get_optional_user)):
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    assert_building_access(user, building_id)

    async def event_generator():
        while True:
            data = await live_data_service.get_live_data(building_id, user=user)
            if data:
                yield f"data: {json.dumps(data.model_dump(mode='json'))}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{building_id}/metrics", response_model=BuildingMetrics)
async def get_metrics(
    building_id: str,
    period: str = "24h",
    user: UserContext = Depends(get_optional_user),
) -> BuildingMetrics:
    assert_building_access(user, building_id)
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    metrics = live_data_service.get_building_metrics(building_id, period, user=user)
    if not metrics:
        if user.is_live_account:
            raise HTTPException(status_code=503, detail=bilingual_error("Metrics unavailable", "المقاييس غير متوفرة"))
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))
    return metrics


@router.post("/{building_id}/test-connection")
async def test_building_connection(
    building_id: str,
    user: UserContext = Depends(require_write_access),
) -> Dict[str, Any]:
    assert_building_access(user, building_id)
    row = await get_building_row(building_id, user.user_id)
    if not row:
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))

    conn = await get_connection(building_id)
    if not conn or not conn.get("host"):
        raise HTTPException(
            status_code=503,
            detail={"code": "NOT_CONFIGURED", "message": bilingual_error("No BMS credentials saved for this building", "لا توجد بيانات BMS محفوظة")},
        )

    client = JCIMetasysClient(
        host=conn.get("host", ""),
        username=conn.get("username", ""),
        password=conn.get("password", ""),
        version=conn.get("protocol_version", "v4"),
        demo_mode=False,
    )
    result = await client.test_connection(conn["host"], conn["username"], conn.get("password", ""), conn.get("protocol_version", "v4"))
    status = "connected" if result.get("status") == "connected" else "error"
    await update_connection_status(building_id, status)
    return result


@router.post("/{building_id}/import-excel")
async def import_building_excel(
    building_id: str,
    file: UploadFile = File(...),
    user: UserContext = Depends(require_write_access),
) -> Dict[str, Any]:
    assert_building_access(user, building_id)
    row = await get_building_row(building_id, user.user_id)
    if not row:
        raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))

    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail=bilingual_error("Upload .xlsx or .xls only", "ارفع ملف .xlsx أو .xls فقط"))

    content = await file.read()
    parsed = parse_building_excel(content)
    imported = 0
    if parsed.get("points"):
        imported = await save_points(building_id, parsed["points"])

    return {
        "building_id": building_id,
        "imported_points": imported,
        "summary": parsed["summary"],
        "building_metadata_detected": parsed.get("building_metadata"),
    }


@router.post("/{building_id}/control", response_model=ControlResponse)
async def send_control(
    building_id: str,
    command: ControlCommand,
    user: UserContext = Depends(require_write_access),
) -> ControlResponse:
    assert_building_access(user, building_id)
    if user.is_live_account:
        row = await get_building_row(building_id, user.user_id)
        if not row:
            raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))
    else:
        building = live_data_service.get_building(building_id)
        if not building:
            raise HTTPException(status_code=404, detail=bilingual_error("Building not found", "المبنى غير موجود"))

    return ControlResponse(
        success=True,
        message=bilingual_success(
            f"Command '{command.command}' accepted for {command.target}",
            f"تم قبول الأمر '{command.command}'",
        ),
        building_id=building_id,
        command=command.command,
    )


@router.get("/{building_id}/site-profile")
async def get_building_site_profile(building_id: str, user: UserContext = Depends(get_optional_user)) -> dict:
    assert_building_access(user, building_id)
    return {"building_id": building_id, "site_profile": get_site_profile(building_id)}


@router.put("/{building_id}/site-profile")
async def update_building_site_profile(
    building_id: str,
    body: SiteProfileUpdate,
    user: UserContext = Depends(require_write_access),
) -> dict:
    assert_building_access(user, building_id)
    try:
        saved = set_site_profile(building_id, body.site_profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=bilingual_error(str(exc), str(exc))) from exc
    return {"building_id": building_id, "site_profile": saved}
