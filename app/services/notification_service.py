"""Outbound notification provider gateway.

Provider URLs are environment-managed secrets. API responses expose only configured state,
never provider URLs or credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings

SUPPORTED_CHANNELS = ("email", "microsoft_teams", "slack", "whatsapp", "webhook")


def _provider_urls() -> Dict[str, str]:
    settings = get_settings()
    return {
        "email": settings.notification_email_webhook_url,
        "microsoft_teams": settings.notification_teams_webhook_url,
        "slack": settings.notification_slack_webhook_url,
        "whatsapp": settings.notification_whatsapp_webhook_url,
        "webhook": settings.supabase_alert_webhook_url,
    }


def channel_status() -> Dict[str, Any]:
    urls = _provider_urls()
    channels = [
        {
            "channel": channel,
            "configured": bool(urls.get(channel)),
            "state": "CONFIGURED" if urls.get(channel) else "NOT_CONFIGURED",
        }
        for channel in SUPPORTED_CHANNELS
    ]
    return {
        "channels": channels,
        "configured_channels": [c["channel"] for c in channels if c["configured"]],
        "supported_channels": list(SUPPORTED_CHANNELS),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _payload_for(channel: str, message: str, *, title: Optional[str] = None) -> Dict[str, Any]:
    title = title or "BuildOpt notification"
    if channel == "slack":
        return {"text": f"*{title}*\n{message}"}
    if channel == "microsoft_teams":
        return {"text": f"{title}\n{message}"}
    return {"title": title, "message": message, "source": "buildopt"}


async def send_notification(
    channel: str,
    message: str,
    *,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    if channel not in SUPPORTED_CHANNELS:
        raise ValueError("unsupported_notification_channel")
    url = _provider_urls().get(channel) or ""
    if not url:
        return {
            "channel": channel,
            "sent": False,
            "state": "NOT_CONFIGURED",
            "status_code": None,
        }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(url, json=_payload_for(channel, message, title=title))
        return {
            "channel": channel,
            "sent": response.is_success,
            "state": "SENT" if response.is_success else "FAILED",
            "status_code": response.status_code,
        }
    except Exception:
        return {
            "channel": channel,
            "sent": False,
            "state": "FAILED",
            "status_code": None,
        }
