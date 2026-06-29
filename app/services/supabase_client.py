from datetime import datetime, timezone
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

        row = {
            "id": alert.get("id"),
            "building_id": alert.get("building_id"),
            "equipment_id": alert.get("equipment_id"),
            "severity": alert.get("severity"),
            "category": alert.get("category"),
            "title": alert.get("title"),
            "message": alert.get("message"),
            "message_ar": alert.get("message_ar"),
            "acknowledged": alert.get("acknowledged", False),
            "created_at": alert.get("timestamp"),
        }

        if self.alert_webhook_url:
            if self._push_via_webhook(alert):
                return True

        if self._push_via_rest(row):
            return True

        if self._client is not None:
            for table in ("building_alerts", "alerts"):
                try:
                    self._client.table(table).upsert(row).execute()
                    return True
                except Exception:
                    continue
        return False

    def _push_via_rest(self, row: Dict[str, Any]) -> bool:
        auth_key = self.service_key or self.key
        if not self.url or not auth_key:
            return False
        headers = {
            "apikey": auth_key,
            "Authorization": f"Bearer {auth_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }
        for table in ("building_alerts", "alerts"):
            try:
                response = httpx.post(
                    f"{self.url.rstrip('/')}/rest/v1/{table}",
                    headers=headers,
                    json=row,
                    timeout=10.0,
                )
                if response.status_code in (200, 201, 204):
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

    def acknowledge_alert(self, alert_id: str, acknowledged_by: Optional[str] = None) -> bool:
        if self.demo_mode:
            return True

        row = {"acknowledged": True, "updated_at": datetime.now(timezone.utc).isoformat()}
        if acknowledged_by:
            row["acknowledged_by"] = acknowledged_by

        auth_key = self.service_key or self.key
        if self._client is not None:
            for table in ("building_alerts", "alerts"):
                try:
                    self._client.table(table).update(row).eq("id", alert_id).execute()
                    return True
                except Exception:
                    continue

        if self.url and auth_key:
            headers = {
                "apikey": auth_key,
                "Authorization": f"Bearer {auth_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            }
            for table in ("building_alerts", "alerts"):
                try:
                    response = httpx.patch(
                        f"{self.url.rstrip('/')}/rest/v1/{table}",
                        headers=headers,
                        params={"id": f"eq.{alert_id}"},
                        json=row,
                        timeout=10.0,
                    )
                    if response.status_code in (200, 204):
                        return True
                except Exception:
                    continue
        return True

    def anonymize_user_id(self, user_id: Optional[str]) -> str:
        if not user_id:
            return "anonymous"
        return f"user_{hash(user_id) % 100000:05d}"
