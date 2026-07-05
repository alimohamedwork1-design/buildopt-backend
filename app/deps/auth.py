from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from app.config import get_settings
from app.models.user_context import UserContext
from app.services.account_service import fetch_user_context


async def _resolve_user(token: str) -> UserContext:
    ctx = await fetch_user_context(token)
    if not ctx:
        raise HTTPException(status_code=401, detail={"en": "Invalid or expired token", "ar": "رمز غير صالح أو منتهي"})
    return ctx


async def get_optional_user(authorization: Optional[str] = Header(default=None)) -> UserContext:
    settings = get_settings()
    if not authorization or not authorization.startswith("Bearer "):
        if settings.demo_mode:
            return UserContext.anonymous_demo()
        return UserContext.anonymous_live()

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        if settings.demo_mode:
            return UserContext.anonymous_demo()
        return UserContext.anonymous_live()

    return await _resolve_user(token)


async def get_required_user(authorization: Optional[str] = Header(default=None)) -> UserContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"en": "Authentication required", "ar": "المصادقة مطلوبة"})
    token = authorization.split(" ", 1)[1].strip()
    return await _resolve_user(token)
