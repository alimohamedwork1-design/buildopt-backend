from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.models.schemas import LiveBuildingData, EnvironmentData, EnergyData, HVACData

logger = logging.getLogger("buildopt.influx")


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
            except Exception as exc:
                logger.warning("InfluxDB client init failed: %s", exc)
                self._client = None

    def status(self) -> str:
        if self.demo_mode:
            return "simulated"
        if self._client is None:
            return "disconnected"
        try:
            self._client.ping()
            return "connected"
        except Exception as exc:
            logger.warning("InfluxDB ping failed: %s", exc)
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
        except Exception as exc:
            logger.warning("InfluxDB write failed (%s): %s", measurement, exc)
            return False

    def query_metrics(self, building_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        if self.demo_mode or self._client is None:
            return []

        try:
            start = f"-{hours}h"
            flux = f'''
            from(bucket: "{self.bucket}")
              |> range(start: {start})
              |> filter(fn: (r) => r["building_id"] == "{building_id}")
              |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
            '''
            tables = self._client.query_api().query(flux, org=self.org)
            results: List[Dict[str, Any]] = []
            for table in tables:
                for record in table.records:
                    results.append(
                        {
                            "timestamp": record.get_time(),
                            "value": float(record.get_value()),
                            "metric": record.get_field(),
                        }
                    )
            return results
        except Exception as exc:
            logger.warning("InfluxDB query_metrics failed: %s", exc)
            return []

    def write_health_point(self, response_ms: float, status: str = "healthy") -> bool:
        return self.write_point(
            "api_health",
            response_ms,
            tags={"status": status},
        )

    def query_health_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        if self.demo_mode or self._client is None:
            return []

        try:
            start = f"-{hours}h"
            flux = f'''
            from(bucket: "{self.bucket}")
              |> range(start: {start})
              |> filter(fn: (r) => r["_measurement"] == "api_health")
              |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
            '''
            tables = self._client.query_api().query(flux, org=self.org)
            results: List[Dict[str, Any]] = []
            for table in tables:
                for record in table.records:
                    ts = record.get_time()
                    if ts and ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    status_tag = record.values.get("status", "healthy")
                    results.append(
                        {
                            "timestamp": ts.isoformat().replace("+00:00", "Z") if ts else "",
                            "response_ms": int(float(record.get_value())),
                            "status": status_tag,
                        }
                    )
            return results
        except Exception as exc:
            logger.warning("InfluxDB query_health_history failed: %s", exc)
            return []

    def query_hourly_kw(self, building_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Return hourly average total_kw for forecast/savings derivation."""
        if self.demo_mode or self._client is None:
            return []

        try:
            start = f"-{hours}h"
            flux = f'''
            from(bucket: "{self.bucket}")
              |> range(start: {start})
              |> filter(fn: (r) => r["building_id"] == "{building_id}")
              |> filter(fn: (r) => r["_field"] == "value")
              |> filter(fn: (r) => r["_measurement"] == "total_kw" or r["_measurement"] == "hvac_kw")
              |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
            '''
            tables = self._client.query_api().query(flux, org=self.org)
            results: List[Dict[str, Any]] = []
            for table in tables:
                for record in table.records:
                    ts = record.get_time()
                    if ts and ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    results.append(
                        {
                            "timestamp": ts,
                            "value": float(record.get_value()),
                            "metric": record.get_measurement(),
                        }
                    )
            return sorted(results, key=lambda r: r["timestamp"])
        except Exception as exc:
            logger.warning("InfluxDB query_hourly_kw failed: %s", exc)
            return []

    def get_latest_snapshot(self, building_id: str) -> Optional[LiveBuildingData]:
        if self.demo_mode or self._client is None:
            return None

        try:
            flux = f'''
            from(bucket: "{self.bucket}")
              |> range(start: -15m)
              |> filter(fn: (r) => r["building_id"] == "{building_id}")
              |> last()
            '''
            tables = self._client.query_api().query(flux, org=self.org)
            fields: Dict[str, float] = {}
            ts = datetime.now(timezone.utc)
            for table in tables:
                for record in table.records:
                    fields[record.get_field()] = float(record.get_value())
                    ts = record.get_time() or ts

            if not fields:
                return None

            hvac_kw = fields.get("hvac_kw", 195.0)
            total_kw = fields.get("total_kw", hvac_kw * 4.0)
            supply = fields.get("supply_air_temp", 14.0)
            temp_c = fields.get("temp_c", 23.0)
            cop = fields.get("cop", 3.8)
            co2 = int(fields.get("co2_ppm", 600))
            hour = datetime.now(timezone.utc).hour
            tariff = 0.38 if 12 <= hour < 24 else 0.23

            return LiveBuildingData(
                building_id=building_id,
                timestamp=ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc),
                hvac=HVACData(
                    supply_air_temp=supply,
                    return_air_temp=supply + 10,
                    delta_t=10.0,
                    power_kw=hvac_kw,
                    cop=cop,
                ),
                energy=EnergyData(
                    total_kw=total_kw,
                    hvac_kw=hvac_kw,
                    lighting_kw=round(total_kw * 0.15, 1),
                    other_kw=round(total_kw * 0.55, 1),
                    tariff_rate=tariff,
                    cost_per_hour=round(total_kw * tariff, 1),
                ),
                environment=EnvironmentData(
                    temp_c=temp_c,
                    humidity_pct=48.0,
                    co2_ppm=co2,
                    pm25=20.0,
                ),
                active_alerts=0,
                demo_mode=False,
            )
        except Exception as exc:
            logger.warning("InfluxDB get_latest_snapshot failed: %s", exc)
            return None
