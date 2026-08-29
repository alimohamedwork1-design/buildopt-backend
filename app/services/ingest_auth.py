"""Shared ingest authentication and gateway scope validation."""

from __future__ import annotations

from fastapi import Header, HTTPException

from app.config import get_settings
from app.services.telemetry_store import get_telemetry_store
from app.utils.arabic_utils import bilingual_error


def verify_ingest_key(x_api_key: str | None) -> None:
    settings = get_settings()
    is_production = settings.app_env.lower() in ("production", "prod")
    if is_production and not settings.ingest_api_key:
        raise HTTPException(
            status_code=503,
            detail=bilingual_error("Ingest API key not configured", "مفتاح الإدخال غير مُعد"),
        )
    if settings.ingest_api_key and x_api_key != settings.ingest_api_key:
        raise HTTPException(status_code=401, detail=bilingual_error("Invalid API key", "مفتاح API غير صالح"))


def authorize_gateway(
    *,
    gateway_id: str,
    tenant_id: str,
    building_id: str,
    connector_id: str | None = None,
) -> dict:
    store = get_telemetry_store()
    try:
        return store.validate_gateway_scope(
            gateway_id=gateway_id,
            tenant_id=tenant_id,
            building_id=building_id,
            connector_id=connector_id,
        )
    except PermissionError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=403,
            detail=bilingual_error(
                f"Gateway authorization failed: {code}",
                "فشل تفويض البوابة",
            ),
        ) from exc


async def ingest_auth_dependency(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    verify_ingest_key(x_api_key)
