from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class InfluxService:
    def __init__(
        self,
        url: str,
        token: str,
        org: str,
        bucket: str,
        demo_mode: bool = True,
    ) -> None:
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.demo_mode = demo_mode
        self._client = None

        if not demo_mode and token:
            try:
                from influxdb_client import InfluxDBClient

                self._client = InfluxDBClient(url=url, token=token, org=org)
            except Exception:
                self._client = None

    def status(self) -> str:
        if self.demo_mode:
            return "simulated"
        if self._client is None:
            return "disconnected"
        try:
            self._client.ping()
            return "connected"
        except Exception:
            return "disconnected"

    def write_point(
        self,
        measurement: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> bool:
        if self.demo_mode or self._client is None:
            return True

        try:
            from influxdb_client import Point, WritePrecision

            point = Point(measurement).field("value", value).time(datetime.now(timezone.utc), WritePrecision.S)
            for key, tag_value in (tags or {}).items():
                point = point.tag(key, tag_value)

            write_api = self._client.write_api()
            write_api.write(bucket=self.bucket, org=self.org, record=point)
            return True
        except Exception:
            return False

    def query_metrics(self, building_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        if self.demo_mode or self._client is None:
            return []
        return []
