"""Phase 3 telemetry pipeline, registry, security, and queue tests."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.telemetry_pipeline import TelemetryPipeline, stable_event_id
from app.services.telemetry_store import TelemetryStore, reset_telemetry_store


@pytest.fixture(autouse=True)
def fresh_store():
    store = TelemetryStore(":memory:")
    reset_telemetry_store(store)
    yield store
    reset_telemetry_store(None)


@pytest.fixture
def client():
    return TestClient(app)


def test_register_raw_point_and_duplicate_discovery(fresh_store):
    payload = {
        "tenant_id": "tenant-a",
        "building_id": "b1",
        "gateway_id": "gw-1",
        "connector_id": "metasys",
        "source": "metasys",
        "source_point_id": "obj-123",
        "source_name": "AHU1_SAT",
        "raw_unit": "degC",
    }
    fresh_store.register_gateway(
        gateway_id="gw-1", tenant_id="tenant-a", building_id="b1", connector_id="metasys"
    )
    p1 = fresh_store.upsert_raw_point(payload)
    p2 = fresh_store.upsert_raw_point(payload)
    assert p1["id"] == p2["id"]
    points, total = fresh_store.list_points(tenant_id="tenant-a")
    assert total == 1


def test_cross_tenant_gateway_rejected(fresh_store):
    fresh_store.register_gateway(
        gateway_id="gw-1", tenant_id="tenant-a", building_id="b1", connector_id="metasys"
    )
    with pytest.raises(PermissionError):
        fresh_store.validate_gateway_scope(
            gateway_id="gw-1",
            tenant_id="tenant-b",
            building_id="b1",
            connector_id="metasys",
        )


def test_event_idempotency(fresh_store):
    fresh_store.register_gateway(
        gateway_id="gw-1", tenant_id="tenant-a", building_id="b1", connector_id="metasys"
    )
    pipeline = TelemetryPipeline()
    ts = datetime.now(timezone.utc).isoformat()
    reading = {
        "source_point_id": "obj-1",
        "source_name": "SAT",
        "source_timestamp": ts,
        "edge_received_at": ts,
        "value": 13.7,
        "quality": "GOOD",
    }
    r1 = pipeline.process_batch(
        gateway_id="gw-1",
        tenant_id="tenant-a",
        building_id="b1",
        connector_id="metasys",
        readings=[reading],
    )
    r2 = pipeline.process_batch(
        gateway_id="gw-1",
        tenant_id="tenant-a",
        building_id="b1",
        connector_id="metasys",
        readings=[reading],
    )
    assert r1["accepted"] == 1
    assert r2["duplicates"] == 1
    assert r2["accepted"] == 0


def test_malformed_event_rejected(fresh_store):
    fresh_store.register_gateway(
        gateway_id="gw-1", tenant_id="tenant-a", building_id="b1", connector_id="metasys"
    )
    pipeline = TelemetryPipeline()
    result = pipeline.process_batch(
        gateway_id="gw-1",
        tenant_id="tenant-a",
        building_id="b1",
        connector_id="metasys",
        readings=[{"value": 1.0}],
    )
    assert result["rejected"] == 1


def test_three_timestamps_preserved(fresh_store):
    fresh_store.register_gateway(
        gateway_id="gw-1", tenant_id="tenant-a", building_id="b1", connector_id="metasys"
    )
    pipeline = TelemetryPipeline()
    source_ts = "2026-08-29T10:00:00+00:00"
    edge_ts = "2026-08-29T10:00:01+00:00"
    pipeline.process_batch(
        gateway_id="gw-1",
        tenant_id="tenant-a",
        building_id="b1",
        connector_id="metasys",
        readings=[
            {
                "source_point_id": "obj-ts",
                "source_timestamp": source_ts,
                "edge_received_at": edge_ts,
                "value": 21.0,
                "quality": "GOOD",
            }
        ],
    )
    points = fresh_store.list_building_current("b1")
    current = points[0]["current"]
    assert current["last_source_timestamp"].startswith("2026-08-29T10:00:00")
    assert current["last_edge_received_at"].startswith("2026-08-29T10:00:01")
    assert current["last_cloud_received_at"] is not None


def test_quality_normalization(fresh_store):
    from app.services.telemetry_quality import normalize_quality

    src, norm = normalize_quality("bad")
    assert norm == "BAD"
    src2, norm2 = normalize_quality(None, has_value=False)
    assert norm2 == "NO_DATA"


def test_stable_event_id_deterministic():
    ts = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)
    a = stable_event_id(
        gateway_id="gw",
        building_id="b",
        connector_id="metasys",
        source_point_id="p1",
        source_timestamp=ts,
        edge_received_at=ts,
        value=1.0,
    )
    b = stable_event_id(
        gateway_id="gw",
        building_id="b",
        connector_id="metasys",
        source_point_id="p1",
        source_timestamp=ts,
        edge_received_at=ts,
        value=1.0,
    )
    assert a == b


def test_telemetry_batch_api_auth(client, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "test-key")
    monkeypatch.setenv("APP_ENV", "test")
    from app.config import get_settings

    get_settings.cache_clear()

    body = {
        "gateway_id": "gw-x",
        "tenant_id": "t1",
        "building_id": "b1",
        "connector_id": "metasys",
        "readings": [],
    }
    r = client.post("/api/v1/telemetry/batch", json=body)
    assert r.status_code == 401

    r2 = client.post(
        "/api/v1/telemetry/batch",
        json=body,
        headers={"X-API-Key": "test-key"},
    )
    assert r2.status_code == 200


def test_gateway_cannot_spoof_building(client, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "test-key")
    monkeypatch.setenv("APP_ENV", "test")
    from app.config import get_settings

    get_settings.cache_clear()
    headers = {"X-API-Key": "test-key"}
    hb = {
        "gateway_id": "gw-spoof",
        "tenant_id": "t1",
        "building_id": "b1",
        "connector_id": "metasys",
    }
    client.post("/api/v1/gateways/heartbeat", json=hb, headers=headers)
    batch = {
        **hb,
        "readings": [
            {
                "source_point_id": "p1",
                "source_timestamp": datetime.now(timezone.utc).isoformat(),
                "edge_received_at": datetime.now(timezone.utc).isoformat(),
                "value": 10,
                "quality": "GOOD",
            }
        ],
    }
    batch["building_id"] = "other-building"
    r = client.post("/api/v1/telemetry/batch", json=batch, headers=headers)
    assert r.status_code == 403


def _load_edge_queue():
    path = Path(__file__).resolve().parents[1] / "buildopt-edge" / "app" / "storage" / "local_queue.py"
    spec = importlib.util.spec_from_file_location("edge_local_queue_p3", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.LocalQueue


def test_queue_survives_restart(tmp_path):
    LocalQueue = _load_edge_queue()
    db = str(tmp_path / "edge.db")
    q1 = LocalQueue(db)
    q1.enqueue("ev-1", "dedupe-1", {"event_id": "ev-1", "value": 1})
    q1.close()
    q2 = LocalQueue(db)
    assert q2.depth() == 1
    row_id, payload, _ = q2.dequeue_batch()[0]
    assert payload["event_id"] == "ev-1"
    q2.ack(row_id)
    assert q2.depth() == 0


def test_queue_duplicate_event_rejected(tmp_path):
    LocalQueue = _load_edge_queue()
    db = str(tmp_path / "edge2.db")
    q = LocalQueue(db)
    q.enqueue("ev-dup", "dedupe-a", {"event_id": "ev-dup", "value": 1})
    q.enqueue("ev-dup", "dedupe-b", {"event_id": "ev-dup", "value": 2})
    assert q.depth() == 1


def test_gateway_heartbeat_clock_drift(client, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "test-key")
    monkeypatch.setenv("APP_ENV", "test")
    from app.config import get_settings

    get_settings.cache_clear()
    old = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
    r = client.post(
        "/api/v1/gateways/heartbeat",
        json={
            "gateway_id": "gw-drift",
            "tenant_id": "t1",
            "building_id": "b1",
            "edge_clock_at": old,
        },
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["clock_drift_seconds"] is not None
    assert body["clock_drift_seconds"] > 120
