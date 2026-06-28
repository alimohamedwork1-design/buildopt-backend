from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.database import get_supabase_service
from app.services.session_store import list_events, record_event, session_stats
from app.utils.arabic_utils import bilingual_success

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionEvent(BaseModel):
    event_type: str = Field(..., pattern="^(login|logout|page_view|module_open|signup|password_reset)$")
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    module_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.post("/events")
async def track_event(
    event: SessionEvent,
    x_forwarded_for: Optional[str] = Header(default=None, alias="X-Forwarded-For"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> dict:
    meta = {
        **event.metadata,
        "ip_hash": x_forwarded_for[:8] if x_forwarded_for else None,
        "user_agent": user_agent[:120] if user_agent else None,
        "source": "build-opt.site",
    }
    recorded = record_event(
        event_type=event.event_type,
        user_id=event.user_id,
        email=event.email,
        role=event.role,
        module_path=event.module_path,
        metadata=meta,
    )

    settings = get_settings()
    if event.event_type in ("login", "signup") and settings.supabase_alert_webhook_url:
        supabase = get_supabase_service()
        supabase.push_alert({
            "id": recorded["id"],
            "building_id": "platform",
            "severity": "info",
            "category": "Auth",
            "title": f"User {event.event_type}",
            "message": f"Role: {event.role or 'unknown'}",
            "timestamp": recorded["timestamp"],
            "acknowledged": True,
        })

    return {
        "success": True,
        "event_id": recorded["id"],
        "message": bilingual_success("Event recorded", "تم تسجيل الحدث"),
    }


@router.get("/events")
async def get_events(
    limit: int = 50,
    event_type: Optional[str] = None,
) -> List[dict]:
    return list_events(limit=limit, event_type=event_type)


@router.get("/stats")
async def get_stats() -> dict:
    return session_stats()
