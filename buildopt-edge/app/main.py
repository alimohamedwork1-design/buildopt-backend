"""Edge gateway main loop."""

from __future__ import annotations

import asyncio
import json
import logging
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
from app.telemetry.validator import normalize_batch

logging.basicConfig(level=logging.INFO, format="%(asctime)s [edge] %(message)s")
logger = logging.getLogger("buildopt.edge")


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


async def collect_readings(connector: BuildingConnector, mapping: Dict[str, str], building_id: str) -> List[Dict[str, Any]]:
    readings: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()
    for logical_key, object_id in mapping.items():
        value = await connector.read_point(object_id)
        if value is None:
            continue
        if isinstance(value, dict) and "value" in value:
            scalar = value.get("value")
        else:
            scalar = value
        readings.append(
            {
                "building_id": building_id,
                "point_id": logical_key,
                "source_point_id": object_id,
                "timestamp": now,
                "value": float(scalar) if isinstance(scalar, (int, float)) else scalar,
                "source": "metasys",
            }
        )
    return readings


async def run_edge() -> None:
    settings = EdgeSettings.from_env()
    if not settings.building_id:
        raise SystemExit("BUILDING_ID is required")

    queue = LocalQueue(settings.queue_db_path)
    uploader = CloudUploader(settings)
    connector = build_connector(settings)
    mapping = load_mapped_points(settings.mapped_points_file)

    logger.info(
        "Starting gateway=%s building=%s connector=%s cloud=%s",
        settings.gateway_id,
        settings.building_id,
        settings.connector,
        settings.cloud_api_url,
    )

    while True:
        try:
            health = await connector.health()
            status = health.get("status", "OFFLINE")
            if status not in ("ONLINE", "connected"):
                await uploader.send_heartbeat(
                    connector_status=status,
                    queue_depth=queue.depth(),
                    connector_error=health.get("message"),
                )
            else:
                readings = await collect_readings(connector, mapping, settings.building_id)
                if readings:
                    batch = normalize_batch(readings, settings.building_id, settings.gateway_id)
                    ok = await uploader.upload_batch(batch, queue_depth=queue.depth())
                    if not ok:
                        for row in batch:
                            dedupe = f"{row['building_id']}:{row['point_id']}:{row['timestamp']}"
                            queue.enqueue(dedupe, row)
                else:
                    await uploader.send_heartbeat(connector_status="ONLINE", queue_depth=queue.depth())

            for row_id, payload, attempts in queue.dequeue_batch():
                ok = await uploader.upload_batch([payload], queue_depth=queue.depth())
                if ok:
                    queue.ack(row_id)
                else:
                    queue.bump_attempts(row_id)
                    if attempts + 1 >= 10:
                        queue.ack(row_id)
                        logger.warning("Dropped event after max retries id=%s", row_id)

        except ConnectorError as exc:
            logger.warning("Connector error: %s", exc)
            await uploader.send_heartbeat(
                connector_status=exc.code,
                queue_depth=queue.depth(),
                connector_error=str(exc),
            )
        except Exception as exc:
            logger.exception("Edge loop error: %s", exc)

        await asyncio.sleep(settings.poll_interval_seconds)


def main() -> None:
    asyncio.run(run_edge())


if __name__ == "__main__":
    main()
