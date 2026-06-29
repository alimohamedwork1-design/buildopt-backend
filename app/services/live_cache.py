from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

from app.models.schemas import Alert, FDDResult, LiveBuildingData


class LiveDataCache:
    """Thread-safe in-memory cache of latest live snapshots per building."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._live: Dict[str, LiveBuildingData] = {}
        self._alerts: List[Alert] = []
        self._fdd_results: List[FDDResult] = []
        self._dewa_tariff: Optional[Dict[str, Any]] = None
        self._prayer_times: Optional[Dict[str, Any]] = None

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

    def acknowledge_alert(self, alert_id: str, acknowledged_by: Optional[str] = None) -> bool:
        with self._lock:
            for alert in self._alerts:
                if alert.id == alert_id:
                    alert.acknowledged = True
                    return True
        return False

    def set_fdd_results(self, results: List[FDDResult]) -> None:
        with self._lock:
            self._fdd_results = results

    def get_fdd_results(self) -> List[FDDResult]:
        with self._lock:
            return list(self._fdd_results)

    def set_dewa_tariff(self, tariff: Dict[str, Any]) -> None:
        with self._lock:
            self._dewa_tariff = tariff

    def get_dewa_tariff(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._dewa_tariff

    def set_prayer_times(self, times: Dict[str, Any]) -> None:
        with self._lock:
            self._prayer_times = times

    def get_prayer_times(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._prayer_times


live_cache = LiveDataCache()
