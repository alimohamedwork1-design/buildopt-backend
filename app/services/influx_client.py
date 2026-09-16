from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.models.schemas import LiveBuildingData, EnvironmentData, EnergyData, HVACData

logger = logging.getLogger("buildopt.influx")

ALLOWED_AGGREGATE_WINDOWS = frozenset({"1m", "5m", "15m", "30m", "1h", "2h"})
MAX_HISTORY_HOURS = 168
MAX_FORECAST_HISTORY_HOURS = 1440
MAX_HISTORY_POINTS = 2000


def _flux_safe_tag(value: str) -> str:
    import re

    if not value or not re.fullmatch(r"[\w\-.:]+", value):
        raise ValueError("invalid_flux_tag")
    return value.replace('"', "")


def _clamp_hours(hours: int) -> int:
    return max(1, min(int(hours), MAX_HISTORY_HOURS))


def _clamp_forecast_hours(hours: int) -> int:
    return max(1, min(int(hours), MAX_FORECAST_HISTORY_HOURS))


def _normalize_every(every: str) -> str:
    normalized = (every or "15m").strip()
    if normalized not in ALLOWED_AGGREGATE_WINDOWS:
        raise ValueError("invalid_aggregate_window")
    return normalized


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
        *,
        timestamp: Optional[datetime] = None,
        fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if self.demo_mode or self._client is None:
            return True

        try:
            from influxdb_client import Point, WritePrecision

            ts = timestamp or datetime.now(timezone.utc)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            point = Point(measurement).field("value", value).time(ts, WritePrecision.S)
            for key, tag_value in (tags or {}).items():
                point = point.tag(key, str(tag_value))
            for key, field_value in (fields or {}).items():
                if isinstance(field_value, bool):
                    point = point.field(key, field_value)
                elif isinstance(field_value, (int, float)):
                    point = point.field(key, float(field_value))
                elif field_value is not None:
                    point = point.field(key, str(field_value))

            write_api = self._client.write_api()
            write_api.write(bucket=self.bucket, org=self.org, record=point)
            return True
        except Exception as exc:
            logger.warning("InfluxDB write failed (%s): %s", measurement, exc)
            return False

    def write_telemetry_rows(self, rows: List[Dict[str, Any]]) -> int:
        """Write validated telemetry rows preserving source timestamps."""
        if self.demo_mode or self._client is None:
            return len(rows)
        stored = 0
        for row in rows:
            if self.write_point(
                measurement=row.get("measurement", "telemetry_point"),
                value=row["value"],
                tags=row.get("tags"),
                timestamp=row.get("timestamp"),
                fields=row.get("fields"),
            ):
                stored += 1
        return stored

    def infrastructure_state(self) -> Dict[str, Any]:
        status = self.status()
        return {
            "configured": bool(self.token) and not self.demo_mode,
            "status": status,
            "url": self.url if status != "simulated" else None,
            "bucket": self.bucket if status != "simulated" else None,
            "persistence": status == "connected",
        }

    def query_metrics(self, building_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        if self.demo_mode or self._client is None:
            return []

        try:
            safe_building = _flux_safe_tag(building_id)
            hours = _clamp_hours(hours)
            start = f"-{hours}h"
            flux = f'''
            from(bucket: "{self.bucket}")
              |> range(start: {start})
              |> filter(fn: (r) => r["building_id"] == "{safe_building}")
              |> filter(fn: (r) => r["_field"] == "value")
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
                            # Measurements such as total_kw/hvac_kw are written with the
                            # generic field name `value`; measurement is the metric identity.
                            "metric": record.get_measurement(),
                        }
                    )
            return sorted(results, key=lambda r: r["timestamp"])
        except ValueError as exc:
            logger.warning("InfluxDB query_metrics invalid input: %s", exc)
            return []
        except Exception as exc:
            logger.warning("InfluxDB query_metrics failed: %s", exc)
            return []

    def write_health_point(self, response_ms: float, status: str = "healthy") -> bool:
        return self.write_point("api_health", response_ms, tags={"status": status})

    def query_health_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        if self.demo_mode or self._client is None:
            return []

        try:
            hours = _clamp_hours(hours)
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
                    results.append({
                        "timestamp": ts.isoformat().replace("+00:00", "Z") if ts else "",
                        "response_ms": int(float(record.get_value())),
                        "status": status_tag,
                    })
            return results
        except Exception as exc:
            logger.warning("InfluxDB query_health_history failed: %s", exc)
            return []

    def query_telemetry_point_history(
        self,
        *,
        point_id: str,
        building_id: str,
        hours: int = 24,
        every: str = "5m",
    ) -> List[Dict[str, Any]]:
        """Return time-series for a registry point from telemetry_point measurement."""
        if self.demo_mode or self._client is None:
            return []

        try:
            hours = _clamp_hours(hours)
            every = _normalize_every(every)
            safe_building = _flux_safe_tag(building_id)
            safe_point = _flux_safe_tag(point_id)
            start = f"-{hours}h"
            flux = f'''
            from(bucket: "{self.bucket}")
              |> range(start: {start})
              |> filter(fn: (r) => r["_measurement"] == "telemetry_point")
              |> filter(fn: (r) => r["building_id"] == "{safe_building}")
              |> filter(fn: (r) => r["point_id"] == "{safe_point}")
              |> filter(fn: (r) => r["_field"] == "value" or r["_field"] == "quality")
              |> aggregateWindow(every: {every}, fn: last, createEmpty: false)
              |> limit(n: {MAX_HISTORY_POINTS * 2})
            '''
            tables = self._client.query_api().query(flux, org=self.org)
            by_ts: Dict[str, Dict[str, Any]] = {}
            for table in tables:
                for record in table.records:
                    ts = record.get_time()
                    if ts and ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    key = ts.isoformat().replace("+00:00", "Z") if ts else ""
                    row = by_ts.setdefault(key, {"timestamp": key, "point_id": point_id})
                    field = record.get_field()
                    if field == "value":
                        row["value"] = float(record.get_value())
                    elif field == "quality":
                        row["quality"] = str(record.get_value())
            results = [r for r in by_ts.values() if "value" in r]
            return sorted(results, key=lambda r: r["timestamp"])
        except ValueError as exc:
            logger.warning("InfluxDB query_telemetry_point_history invalid input: %s", exc)
            return []
        except Exception as exc:
            logger.warning("InfluxDB query_telemetry_point_history failed: %s", exc)
            return []

    def query_building_telemetry_history(
        self,
        building_id: str,
        *,
        hours: int = 24,
        every: str = "15m",
        point_ids: Optional[List[str]] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Aggregate telemetry_point history for a building (optionally filtered by point_ids)."""
        if self.demo_mode or self._client is None:
            return []

        try:
            hours = _clamp_hours(hours)
            every = _normalize_every(every)
            safe_building = _flux_safe_tag(building_id)
            row_limit = max(1, min(int(limit), MAX_HISTORY_POINTS))
            start = f"-{hours}h"
            point_filter = ""
            if point_ids:
                safe_ids = [_flux_safe_tag(pid) for pid in point_ids[:20]]
                ids = " or ".join(f'r["point_id"] == "{pid}"' for pid in safe_ids)
                point_filter = f'|> filter(fn: (r) => {ids})'
            flux = f'''
            from(bucket: "{self.bucket}")
              |> range(start: {start})
              |> filter(fn: (r) => r["_measurement"] == "telemetry_point")
              |> filter(fn: (r) => r["building_id"] == "{safe_building}")
              |> filter(fn: (r) => r["_field"] == "value")
              {point_filter}
              |> aggregateWindow(every: {every}, fn: mean, createEmpty: false)
              |> limit(n: {row_limit})
            '''
            tables = self._client.query_api().query(flux, org=self.org)
            results: List[Dict[str, Any]] = []
            for table in tables:
                for record in table.records:
                    ts = record.get_time()
                    if ts and ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    results.append({
                        "timestamp": ts.isoformat().replace("+00:00", "Z") if ts else "",
                        "value": float(record.get_value()),
                        "point_id": record.values.get("point_id", ""),
                        "source_point_id": record.values.get("source_point_id", ""),
                    })
            return sorted(results, key=lambda r: r["timestamp"])
        except ValueError as exc:
            logger.warning("InfluxDB query_building_telemetry_history invalid input: %s", exc)
            return []
        except Exception as exc:
            logger.warning("InfluxDB query_building_telemetry_history failed: %s", exc)
            return []

    def query_hourly_kw(self, building_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Return hourly average total_kw/hvac_kw for forecast and M&V derivation."""
        if self.demo_mode or self._client is None:
            return []

        try:
            safe_building = _flux_safe_tag(building_id)
            hours = _clamp_forecast_hours(hours)
            start = f"-{hours}h"
            flux = f'''
            from(bucket: "{self.bucket}")
              |> range(start: {start})
              |> filter(fn: (r) => r["building_id"] == "{safe_building}")
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
                    results.append({
                        "timestamp": ts,
                        "value": float(record.get_value()),
                        "metric": record.get_measurement(),
                    })
            return sorted(results, key=lambda r: r["timestamp"])
        except ValueError as exc:
            logger.warning("InfluxDB query_hourly_kw invalid input: %s", exc)
            return []
        except Exception as exc:
            logger.warning("InfluxDB query_hourly_kw failed: %s", exc)
            return []

    def get_latest_snapshot(self, building_id: str) -> Optional[LiveBuildingData]:
        if self.demo_mode or self._client is None:
            return None

        try:
            safe_building = _flux_safe_tag(building_id)
            flux = f'''
            from(bucket: "{self.bucket}")
              |> range(start: -15m)
              |> filter(fn: (r) => r["building_id"] == "{safe_building}")
              |> filter(fn: (r) => r["_field"] == "value")
              |> last()
            '''
            tables = self._client.query_api().query(flux, org=self.org)
            measurements: Dict[str, float] = {}
            ts = datetime.now(timezone.utc)
            for table in tables:
                for record in table.records:
                    measurement = str(record.get_measurement() or "")
                    if measurement:
                        measurements[measurement] = float(record.get_value())
                    ts = record.get_time() or ts

            required = {
                "total_kw",
                "hvac_kw",
                "lighting_kw",
                "other_kw",
                "supply_air_temp",
                "return_air_temp",
                "temp_c",
                "humidity_pct",
                "co2_ppm",
                "pm25",
                "cop",
            }
            if not required.issubset(measurements):
                return None

            total_kw = measurements["total_kw"]
            hvac_kw = measurements["hvac_kw"]
            hour = datetime.now(timezone.utc).hour
            tariff = 0.38 if 12 <= hour < 24 else 0.23

            return LiveBuildingData(
                building_id=building_id,
                timestamp=ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc),
                hvac=HVACData(
                    supply_air_temp=measurements["supply_air_temp"],
                    return_air_temp=measurements["return_air_temp"],
                    delta_t=round(measurements["return_air_temp"] - measurements["supply_air_temp"], 2),
                    power_kw=hvac_kw,
                    cop=measurements["cop"],
                ),
                energy=EnergyData(
                    total_kw=total_kw,
                    hvac_kw=hvac_kw,
                    lighting_kw=measurements["lighting_kw"],
                    other_kw=measurements["other_kw"],
                    tariff_rate=tariff,
                    cost_per_hour=round(total_kw * tariff, 2),
                ),
                environment=EnvironmentData(
                    temp_c=measurements["temp_c"],
                    humidity_pct=measurements["humidity_pct"],
                    co2_ppm=int(measurements["co2_ppm"]),
                    pm25=measurements["pm25"],
                ),
                active_alerts=0,
                demo_mode=False,
                source="influx",
            )
        except ValueError as exc:
            logger.warning("InfluxDB get_latest_snapshot invalid input: %s", exc)
            return None
        except Exception as exc:
            logger.warning("InfluxDB get_latest_snapshot failed: %s", exc)
            return None
