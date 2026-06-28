from typing import Any, Dict, Optional


class SupabaseService:
    def __init__(
        self,
        url: str,
        key: str,
        service_key: str,
        demo_mode: bool = True,
    ) -> None:
        self.url = url
        self.key = key
        self.service_key = service_key
        self.demo_mode = demo_mode
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
        return "connected" if self._client else "disconnected"

    def push_alert(self, alert: Dict[str, Any]) -> bool:
        if self.demo_mode or self._client is None:
            return True
        try:
            self._client.table("alerts").insert(alert).execute()
            return True
        except Exception:
            return False

    def anonymize_user_id(self, user_id: Optional[str]) -> str:
        if not user_id:
            return "anonymous"
        return f"user_{hash(user_id) % 100000:05d}"
