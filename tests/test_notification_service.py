from __future__ import annotations

import pytest

from app.config import get_settings
from app.services.notification_service import channel_status, send_notification


def test_notification_status_does_not_expose_provider_urls(monkeypatch):
    monkeypatch.setenv("NOTIFICATION_SLACK_WEBHOOK_URL", "https://hooks.example.invalid/secret-path")
    get_settings.cache_clear()
    try:
        status = channel_status()
    finally:
        get_settings.cache_clear()

    slack = next(c for c in status["channels"] if c["channel"] == "slack")
    assert slack["configured"] is True
    assert slack["state"] == "CONFIGURED"
    rendered = str(status)
    assert "secret-path" not in rendered
    assert "https://" not in rendered


@pytest.mark.asyncio
async def test_unconfigured_notification_is_not_claimed_sent(monkeypatch):
    monkeypatch.setenv("NOTIFICATION_EMAIL_WEBHOOK_URL", "")
    get_settings.cache_clear()
    try:
        result = await send_notification("email", "test")
    finally:
        get_settings.cache_clear()

    assert result["sent"] is False
    assert result["state"] == "NOT_CONFIGURED"
    assert result["status_code"] is None


@pytest.mark.asyncio
async def test_unsupported_notification_channel_is_rejected():
    with pytest.raises(ValueError, match="unsupported_notification_channel"):
        await send_notification("sms", "test")
