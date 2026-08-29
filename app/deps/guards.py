from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException

from app.models.user_context import UserContext
from app.deps.auth import get_optional_user, get_required_user
from app.models.schemas import BilingualMessage, EmptyDataPayload
from app.utils.arabic_utils import bilingual_error


def empty_no_building() -> Dict[str, Any]:
    payload = EmptyDataPayload(
        empty_state=True,
        reason="no_building_connected",
        message=BilingualMessage(
            en="No building connected. Add a building and connect your BMS to start reading live data.",
            ar="لا يوجد مبنى متصل. أضف مبنى واربط نظام BMS لبدء قراءة البيانات الحية.",
        ),
        actions=["connect_building", "read_data"],
    )
    return payload.model_dump()


def require_admin(user: UserContext = Depends(get_required_user)) -> UserContext:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail=bilingual_error("Admin access required", "يتطلب صلاحيات المسؤول"))
    return user


def require_write_access(user: UserContext = Depends(get_required_user)) -> UserContext:
    if user.is_read_only:
        raise HTTPException(
            status_code=403,
            detail=bilingual_error("Read-only account — writes are disabled", "حساب للقراءة فقط — التعديلات معطلة"),
        )
    return user


_SEMANTIC_WRITE_ROLES = frozenset({"admin", "bms_integrator", "energy_engineer", "facility_manager"})


def require_semantic_write(user: UserContext = Depends(get_required_user)) -> UserContext:
    """Engineer/admin/integrator — approve, reject, edit, revert semantic mappings."""
    if user.is_read_only:
        raise HTTPException(status_code=403, detail=bilingual_error("Read-only account", "حساب للقراءة فقط"))
    if user.is_admin:
        return user
    if not _SEMANTIC_WRITE_ROLES.intersection(set(user.roles)):
        raise HTTPException(
            status_code=403,
            detail=bilingual_error("Semantic write access required", "يتطلب صلاحيات تعديل التعيين الدلالي"),
        )
    return user


def require_module_enabled(module_slug: str):
    async def _guard(user: UserContext = Depends(get_optional_user)) -> UserContext:
        if user.allows_demo_data():
            return user
        if not user.authenticated:
            raise HTTPException(status_code=401, detail=bilingual_error("Authentication required", "المصادقة مطلوبة"))
        if user.is_admin:
            return user
        if module_slug not in user.enabled_modules:
            raise HTTPException(
                status_code=403,
                detail=bilingual_error(f"Module '{module_slug}' is disabled for this account", f"الوحدة '{module_slug}' معطلة لهذا الحساب"),
            )
        return user

    return _guard


async def require_real_data_or_empty(
    user: UserContext = Depends(get_optional_user),
) -> UserContext:
    """Live accounts without buildings must not receive demo payloads downstream."""
    return user


def assert_building_access(user: UserContext, building_id: str) -> None:
    if user.allows_demo_data():
        return
    if not user.authenticated:
        raise HTTPException(status_code=401, detail=bilingual_error("Authentication required", "المصادقة مطلوبة"))
    if not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    if building_id not in user.building_ids and not user.is_admin:
        raise HTTPException(status_code=403, detail=bilingual_error("Building not accessible", "المبنى غير متاح"))


def block_demo_fallback_for_live(user: UserContext) -> None:
    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
