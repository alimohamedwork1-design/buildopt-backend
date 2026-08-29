"""Edge gateway main loop — poll, discover, upload, store-and-forward."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.config import EdgeSettings
from app.connectors.bacnet import BacnetConnector
from app.connectors.base import BuildingConnector, ConnectorError
from app.connectors.metasys import MetasysConnector
from app.connectors.modbus import ModbusConnector
from app.connectors.mqtt import MqttConnector
from app.connectors.opcua import OpcUaConnector
from app.security.credentials import load_metasys_credentials
from app.storage.local_queue import LocalQueue
from app.telemetry.uploader import CloudUploader
from app.telemetry.validator import normalize_batch, stable_event_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s [edge] %(message)s")
logger = logging.getLogger("buildopt.edge")

_shutdown = False


def _handle_shutdown(*_args: Any) -> None:
    global _shutdown
    _shutdown = True
    logger.info("Graceful shutdown requested")


def build_connector(settings: EdgeSettings) -> BuildingConnector:
    name = settings.connector
    if name == "metasys":
        creds = load_metasys_credentials(
            settings.metasys_host,
            settings.metasys_username,
            settings.metasys_password,
        )
        if not creds:
            raise ConnectorError("NOT_CONFIGURED", "Metasys credentials missing")
        return MetasysConnector(creds.host, creds.username, creds.password, settings.metasys_version)
    if name == "bacnet":
        return BacnetConnector()
    if name == "modbus":
        return ModbusConnector()
    if name == "mqtt":
        return MqttConnector()
    if name == "opcua":
        return OpcUaConnector()
    raise ConnectorError("NOT_CONFIGURED", f"Unknown connector {name}")


def load_mapped_points(path: str) -> Dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


async def collect_readings(
    connector: BuildingConnector,
    mapping: Dict[str, str],
    building_id: str,
    gateway_id: str,
    connector_id: str,
    tenant_id: str,
) -> List[Dict[str, Any]]:
    readings: List[Dict[str, Any]] = []
    edge_received_at = datetime.now(timezone.utc).isoformat()
    for logical_key, object_id in mapping.items():
        value = await connector.read_point(object_id)
        if value is None:
            continue
        source_timestamp = edge_received_at
        quality = "UNCERTAIN"
        if isinstance(value, dict):
            scalar = value.get("value")
            if value.get("timestamp"):
                source_timestamp = str(value["timestamp"])
            if value.get("quality"):
                quality = str(value["quality"])
        else:
            scalar = value
        event_id = stable_event_id(
            gateway_id=gateway_id,
            building_id=building_id,
            connector_id=connector_id,
            source_point_id=object_id,
            source_timestamp=source_timestamp,
            value=scalar,
        )
        readings.append(
            {
                "building_id": building_id,
                "gateway_id": gateway_id,
                "connector_id": connector_id,
                "tenant_id": tenant_id,
                "point_id": logical_key,
                "source_point_id": object_id,
                "source_name": logical_key,
                "source_timestamp": source_timestamp,
                "edge_received_at": edge_received_at,
                "event_id": event_id,
                "value": float(scalar) if isinstance(scalar, (int, float)) else scalar,
                "quality": quality,
                "source": connector_id,
            }
        )
    return readings


def mapping_to_discovery_points(mapping: Dict[str, str], connector_id: str) -> List[Dict[str, Any]]:
    return [
        {
            "source": connector_id,
            "source_point_id": object_id,
            "source_name": logical_key,
            "source_path": object_id,
            "source_type": "analog",
        }
        for logical_key, object_id in mapping.items()
    ]


async def resolve_collection_mapping(settings: EdgeSettings, uploader: CloudUploader) -> Dict[str, str]:
    """Bootstrap mapped_points.json first; else approved cloud collection config."""
    bootstrap = load_mapped_points(settings.mapped_points_file)
    if bootstrap:
        logger.info("Using bootstrap mapped_points.json (%d approved keys)", len(bootstrap))
        return bootstrap
    cloud_mapping = await uploader.fetch_collection_config()
    if cloud_mapping:
        logger.info("Using approved cloud collection config (%d keys)", len(cloud_mapping))
        return cloud_mapping
    logger.error(
        "NOT CONFIGURED — no bootstrap mapped_points.json and no approved cloud collection config"
    )
    return {}


async def run_edge() -> None:
    global _shutdown
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    settings = EdgeSettings.from_env()
    if not settings.building_id:
        raise SystemExit("BUILDING_ID is required")

    queue = LocalQueue(settings.queue_db_path)
    uploader = CloudUploader(settings)
    connector = build_connector(settings)
    mapping = await resolve_collection_mapping(settings, uploader)

    if mapping:
        await uploader.sync_discovery(mapping_to_discovery_points(mapping, settings.connector))
    else:
        await uploader.send_heartbeat(
            connector_status="NOT_CONFIGURED",
            connector_error="No approved collection config or bootstrap mapping",
        )

    logger.info(
        "Starting gateway=%s building=%s connector=%s cloud=%s",
        settings.gateway_id,
        settings.building_id,
        settings.connector,
        settings.cloud_api_url,
    )

    while not _shutdown:
        try:
            q_metrics = queue.metrics()
            health = await connector.health()
            status = health.get("status", "OFFLINE")
            if status not in ("ONLINE", "connected"):
                await uploader.send_heartbeat(
                    connector_status=status,
                    queue_depth=q_metrics["queue_depth"],
                    oldest_queued_event_seconds=q_metrics["oldest_queued_event_seconds"],
                    connector_error=health.get("message"),
                )
            else:
                if not mapping:
                    await uploader.send_heartbeat(
                        connector_status="NOT_CONFIGURED",
                        queue_depth=q_metrics["queue_depth"],
                        oldest_queued_event_seconds=q_metrics["oldest_queued_event_seconds"],
                        connector_error="Awaiting approved collection config",
                    )
                else:
                    readings = await collect_readings(
                        connector,
                        mapping,
                        settings.building_id,
                        settings.gateway_id,
                        settings.connector,
                        settings.tenant_id,
                    )
                    if readings:
                        batch = normalize_batch(
                            readings,
                            settings.building_id,
                            settings.gateway_id,
                            settings.connector,
                            settings.tenant_id,
                        )
                        ok = await uploader.upload_batch(
                            batch,
                            queue_depth=q_metrics["queue_depth"],
                            oldest_queued_event_seconds=q_metrics["oldest_queued_event_seconds"],
                        )
                        if not ok:
                            for row in batch:
                                uploader.events_queued_total += 1
                                dedupe = f"{row['building_id']}:{row['source_point_id']}:{row['source_timestamp']}"
                                queue.enqueue(row["event_id"], dedupe, row)
                    else:
                        await uploader.send_heartbeat(
                            connector_status="ONLINE",
                            queue_depth=q_metrics["queue_depth"],
                            oldest_queued_event_seconds=q_metrics["oldest_queued_event_seconds"],
                        )

            for row_id, payload, attempts in queue.dequeue_batch():
                qm = queue.metrics()
                ok = await uploader.upload_batch(
                    [payload],
                    queue_depth=qm["queue_depth"],
                    oldest_queued_event_seconds=qm["oldest_queued_event_seconds"],
                    replay=True,
                )
                if ok:
                    queue.ack(row_id)
                else:
                    new_attempts = queue.bump_attempts(row_id)
                    if new_attempts >= queue.max_attempts:
                        logger.critical(
                            "Event id=%s exceeded max retries — retained in queue (no silent delete)",
                            payload.get("event_id"),
                        )

        except ConnectorError as exc:
            logger.warning("Connector error: %s", exc)
            qm = queue.metrics()
            await uploader.send_heartbeat(
                connector_status=exc.code,
                queue_depth=qm["queue_depth"],
                oldest_queued_event_seconds=qm["oldest_queued_event_seconds"],
                connector_error=str(exc),
            )
        except Exception as exc:
            logger.exception("Edge loop error: %s", exc)

        await asyncio.sleep(settings.poll_interval_seconds)

    queue.close()
    logger.info("Edge gateway stopped gracefully")


def main() -> None:
    asyncio.run(run_edge())


if __name__ == "__main__":
    main()
