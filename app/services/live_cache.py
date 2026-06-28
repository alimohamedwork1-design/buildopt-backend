from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional

from app.models.schemas import Alert, LiveBuildingData


class LiveDataCache:
    """Thread-safe in-memory cache of latest live snapshots per building."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._live: Dict[str, LiveBuildingData] = {}
        self._alerts: List[Alert] = []

    def set_live(self, building_id: str, data: LiveBuildingData) -> None:
        with self._lock:
            self._live[building_id] = data

    def get_live(self, building_id: str) -> Optional[LiveBuildingData]:
        with self._lock:
            return self._live.get(building_id)

    def list_live_ids(self) -> List[str]:
        with self._lock:
            return list(self._live.keys())

    def set_alerts(self, alerts: List[Alert]) -> None:
        with self._lock:
            self._alerts = alerts

    def get_alerts(self) -> List[Alert]:
        with self._lock:
            return list(self._alerts)


live_cache = LiveDataCache()
