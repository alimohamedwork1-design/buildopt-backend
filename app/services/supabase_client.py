from typing import Any, Dict, Optional

import httpx

from app.config import get_settings


class SupabaseService:
    def __init__(
        self,
        url: str,
        key: str,
        service_key: str,
        demo_mode: bool = True,
        alert_webhook_url: str = "",
        alert_webhook_secret: str = "",
    ) -> None:
        self.url = url
        self.key = key
        self.service_key = service_key
        self.demo_mode = demo_mode
        self.alert_webhook_url = alert_webhook_url
        self.alert_webhook_secret = alert_webhook_secret
        self._client = None

        if not demo_mode and url and service_key:
            try:
                from supabase import create_client

                self._client = create_client(url, service_key)
            except Exception:
                self._client = None

    def status(self) -> str:
        if self.demo_mode:
            return "simulated"
        if self._client:
            return "connected"
        if self.alert_webhook_url:
            return "webhook"
        return "not_configured"

    def push_alert(self, alert: Dict[str, Any]) -> bool:
        if self.demo_mode:
            return True

        if self.alert_webhook_url:
            return self._push_via_webhook(alert)

        if self._client is None:
            return True

        row = {
            "id": alert.get("id"),
            "building_id": alert.get("building_id"),
            "severity": alert.get("severity"),
            "category": alert.get("category"),
            "title": alert.get("title"),
            "message": alert.get("message"),
            "acknowledged": alert.get("acknowledged", False),
            "created_at": alert.get("timestamp"),
        }
        for table in ("alerts", "building_alerts"):
            try:
                self._client.table(table).upsert(row).execute()
                return True
            except Exception:
                continue
        return False

    def _push_via_webhook(self, alert: Dict[str, Any]) -> bool:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.key}" if self.key else "",
        }
        if self.alert_webhook_secret:
            headers["x-buildopt-secret"] = self.alert_webhook_secret
        try:
            response = httpx.post(
                self.alert_webhook_url,
                json=alert,
                headers=headers,
                timeout=10.0,
            )
            return response.status_code in (200, 201, 204)
        except Exception:
            return False

    def anonymize_user_id(self, user_id: Optional[str]) -> str:
        if not user_id:
            return "anonymous"
        return f"user_{hash(user_id) % 100000:05d}"
