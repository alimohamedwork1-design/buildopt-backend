"""FDD fault API — live semantic-driven fault detection."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.deps.auth import UserContext, get_optional_user
from app.deps.guards import assert_building_access, require_module_enabled, require_write_access
from app.services.fdd_fault_store import get_fdd_fault_store
from app.services.fdd_rule_framework import FddRuleEngine
from app.services.semantic_readings_service import build_semantic_readings
from app.services.telemetry_store import get_telemetry_store
from app.utils.arabic_utils import bilingual_error, bilingual_success
from pydantic import BaseModel

router = APIRouter(prefix="/fdd", tags=["fdd"])


class FaultTransitionRequest(BaseModel):
    status: str
    comment: Optional[str] = None


@router.get("/buildings/{building_id}/faults")
async def list_building_faults(
    building_id: str,
    active_only: bool = True,
    user: UserContext = Depends(require_module_enabled("fdd")),
) -> dict:
    assert_building_access(user, building_id)
    store = get_fdd_fault_store()
    faults = store.list_active(building_id) if active_only else store.list_all(building_id)
    return {"building_id": building_id, "faults": faults, "total": len(faults)}


@router.post("/buildings/{building_id}/evaluate")
async def evaluate_building_fdd(
    building_id: str,
    equipment_id: Optional[str] = None,
    user: UserContext = Depends(require_module_enabled("fdd")),
) -> dict:
    assert_building_access(user, building_id)
    ts = get_telemetry_store()
    readings, meta, approved = build_semantic_readings(ts, building_id=building_id, equipment_id=equipment_id)
    if not readings:
        return {
            "building_id": building_id,
            "state": "INSUFFICIENT_DATA",
            "faults": [],
            "blocked": [],
            "approved_points": len(approved),
            "message": "NO_DATA — no approved mapped points with current values",
        }

    equipment_ids = {m.get("equipment_id") or "UNASSIGNED" for m in meta.values()}
    engine = FddRuleEngine()
    fault_store = get_fdd_fault_store()
    all_faults = []
    all_blocked = []

    for eq in equipment_ids:
        eq_readings = {k: v for k, v in readings.items() if meta.get(k, {}).get("equipment_id", "UNASSIGNED") == eq}
        eq_meta = {k: v for k, v in meta.items() if v.get("equipment_id", "UNASSIGNED") == eq}
        result = engine.evaluate_equipment(
            readings=eq_readings,
            point_meta=eq_meta,
            equipment_id=eq,
            equipment_type="AHU" if eq != "UNASSIGNED" else "AHU",
            building_id=building_id,
        )
        for fault in result["faults"]:
            fault_store.upsert_fault(fault)
            all_faults.append(fault)
        all_blocked.extend(result["blocked"])

    return {
        "building_id": building_id,
        "state": "OK" if all_faults or all_blocked else "NO_FAULTS",
        "faults": all_faults,
        "blocked": all_blocked,
        "approved_points": len(approved),
    }


@router.post("/faults/{fault_id}/transition")
async def transition_fault(
    fault_id: str,
    body: FaultTransitionRequest,
    user: UserContext = Depends(require_write_access),
) -> dict:
    updated = get_fdd_fault_store().transition(
        fault_id,
        new_status=body.status.upper(),
        actor_user_id=user.user_id,
        comment=body.comment,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=bilingual_error("Fault not found", "العطل غير موجود"))
    return {"fault": updated, "message": bilingual_success("Fault status updated", "تم تحديث حالة العطل")}
