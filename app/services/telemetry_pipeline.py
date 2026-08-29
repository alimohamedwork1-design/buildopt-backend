"""Telemetry validation pipeline — schema, registry, timestamps, quality, dedupe."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services.freshness_engine import apply_quality_state, compute_freshness
from app.services.telemetry_quality import normalize_quality, quality_allows_storage
from app.services.telemetry_store import get_telemetry_store

logger = logging.getLogger("buildopt.telemetry.pipeline")


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def stable_event_id(
    *,
    gateway_id: str,
    building_id: str,
    connector_id: str,
    source_point_id: str,
    source_timestamp: Optional[datetime],
    edge_received_at: Optional[datetime],
    value: Any,
) -> str:
    """Deterministic event ID — stable across replay."""
    ts = source_timestamp or edge_received_at
    ts_part = ts.isoformat() if ts else "no_source_ts"
    raw = f"{gateway_id}|{building_id}|{connector_id}|{source_point_id}|{ts_part}|{value}"
    return hashlib.sha256(raw.encode()).hexdigest()


class TelemetryPipeline:
    def __init__(self) -> None:
        self._store: Any = None

    @property
    def store(self) -> Any:
        if self._store is None:
            self._store = get_telemetry_store()
        return self._store

    def process_batch(
        self,
        *,
        gateway_id: str,
        tenant_id: str,
        building_id: str,
        connector_id: str,
        readings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        cloud_received_at = datetime.now(timezone.utc)
        accepted = 0
        rejected = 0
        duplicates = 0
        stored = 0
        rejections: List[Dict[str, str]] = []
        influx_rows: List[Dict[str, Any]] = []

        self.store.validate_gateway_scope(
            gateway_id=gateway_id,
            tenant_id=tenant_id,
            building_id=building_id,
            connector_id=connector_id,
        )

        for idx, raw in enumerate(readings):
            try:
                result = self._process_one(
                    raw=raw,
                    gateway_id=gateway_id,
                    tenant_id=tenant_id,
                    building_id=building_id,
                    connector_id=connector_id,
                    cloud_received_at=cloud_received_at,
                )
                if result["status"] == "duplicate":
                    duplicates += 1
                elif result["status"] == "accepted":
                    accepted += 1
                    if result.get("influx_row"):
                        influx_rows.append(result["influx_row"])
                        stored += 1
                else:
                    rejected += 1
                    rejections.append({"index": str(idx), "reason": result.get("reason", "rejected")})
            except Exception as exc:
                rejected += 1
                rejections.append({"index": str(idx), "reason": str(exc)})
                logger.warning("Telemetry event rejected idx=%s: %s", idx, exc)

        return {
            "accepted": accepted,
            "rejected": rejected,
            "duplicates": duplicates,
            "stored": stored,
            "rejections": rejections,
            "influx_rows": influx_rows,
            "cloud_received_at": cloud_received_at.isoformat(),
        }

    def _process_one(
        self,
        *,
        raw: Dict[str, Any],
        gateway_id: str,
        tenant_id: str,
        building_id: str,
        connector_id: str,
        cloud_received_at: datetime,
    ) -> Dict[str, Any]:
        source_point_id = raw.get("source_point_id") or raw.get("point_id")
        if not source_point_id:
            return {"status": "rejected", "reason": "missing_source_point_id"}

        if raw.get("building_id") and raw["building_id"] != building_id:
            return {"status": "rejected", "reason": "building_mismatch"}
        if raw.get("tenant_id") and raw["tenant_id"] != tenant_id:
            return {"status": "rejected", "reason": "tenant_mismatch"}

        source_timestamp = _parse_dt(raw.get("source_timestamp") or raw.get("timestamp"))
        edge_received_at = _parse_dt(raw.get("edge_received_at"))
        source_timestamp_missing = source_timestamp is None

        if source_timestamp is None and edge_received_at is None:
            return {"status": "rejected", "reason": "missing_timestamps"}

        value = raw.get("value")
        if value is None:
            return {"status": "rejected", "reason": "missing_value"}

        source_quality_raw = raw.get("source_quality") or raw.get("quality")
        source_quality, normalized_quality = normalize_quality(
            source_quality_raw,
            has_value=value is not None,
        )
        if not quality_allows_storage(normalized_quality):
            return {"status": "rejected", "reason": "invalid_quality"}

        event_id = raw.get("event_id") or stable_event_id(
            gateway_id=gateway_id,
            building_id=building_id,
            connector_id=connector_id,
            source_point_id=str(source_point_id),
            source_timestamp=source_timestamp,
            edge_received_at=edge_received_at,
            value=value,
        )

        if self.store.is_event_processed(event_id):
            return {"status": "duplicate", "event_id": event_id}

        point = self.store.find_point_by_source(
            tenant_id=tenant_id,
            connector_id=connector_id,
            source_point_id=str(source_point_id),
        )
        if not point:
            point = self.store.upsert_raw_point(
                {
                    "tenant_id": tenant_id,
                    "building_id": building_id,
                    "gateway_id": gateway_id,
                    "connector_id": connector_id,
                    "source": raw.get("source", "metasys"),
                    "source_point_id": str(source_point_id),
                    "source_name": raw.get("source_name") or raw.get("point_id"),
                    "source_path": raw.get("source_path"),
                    "source_type": raw.get("source_type"),
                    "raw_unit": raw.get("raw_unit") or raw.get("unit"),
                    "metadata": raw.get("metadata") or {},
                }
            )

        point_id = point["id"]
        interval = int(point.get("expected_interval_seconds") or 30)
        self.store.update_current_state(
            point_id=point_id,
            value=value,
            source_timestamp=source_timestamp,
            edge_received_at=edge_received_at,
            cloud_received_at=cloud_received_at,
            source_quality=source_quality,
            normalized_quality=normalized_quality,
            expected_interval_seconds=interval,
        )
        self.store.mark_event_processed(
            event_id=event_id,
            tenant_id=tenant_id,
            building_id=building_id,
            gateway_id=gateway_id,
        )

        influx_ts = source_timestamp or edge_received_at or cloud_received_at
        influx_row = None
        if isinstance(value, (int, float)):
            influx_row = {
                "measurement": "telemetry_point",
                "value": float(value),
                "timestamp": influx_ts,
                "tags": {
                    "tenant_id": tenant_id,
                    "building_id": building_id,
                    "gateway_id": gateway_id,
                    "connector_id": connector_id,
                    "point_id": point_id,
                    "source_point_id": str(source_point_id),
                    "source": raw.get("source", "metasys"),
                },
                "fields": {
                    "quality": normalized_quality,
                    "source_quality": source_quality or "",
                    "source_timestamp_missing": source_timestamp_missing,
                },
            }

        return {
            "status": "accepted",
            "event_id": event_id,
            "point_id": point_id,
            "influx_row": influx_row,
        }


_pipeline: Optional[TelemetryPipeline] = None


def get_telemetry_pipeline() -> TelemetryPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = TelemetryPipeline()
    return _pipeline
