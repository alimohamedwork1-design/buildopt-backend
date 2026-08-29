"""Supabase telemetry store parity tests (mocked PostgREST)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.supabase_telemetry_store import SupabaseTelemetryStore


@pytest.fixture
def store():
    return SupabaseTelemetryStore("https://example.supabase.co", "test-service-key")


def _mock_response(status_code: int = 200, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = json.dumps(json_data or [])
    resp.json.return_value = json_data or []
    resp.headers = headers or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


def test_register_gateway_identity_mismatch(store):
    with patch.object(store._client, "request") as req:
        req.return_value = _mock_response(
            200,
            [
                {
                    "gateway_id": "gw-1",
                    "tenant_id": "tenant-a",
                    "building_id": "b1",
                    "connector_id": "metasys",
                    "enabled": True,
                }
            ],
        )
        with pytest.raises(PermissionError):
            store.register_gateway(
                gateway_id="gw-1",
                tenant_id="tenant-b",
                building_id="b1",
                connector_id="metasys",
            )


def test_upsert_raw_point_stable_identity(store):
    existing_id = "11111111-1111-1111-1111-111111111111"
    calls = []

    def side_effect(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "GET" and "raw_points" in url:
            if len(calls) == 1:
                return _mock_response(200, [{"id": existing_id}])
            return _mock_response(
                200,
                [
                    {
                        "id": existing_id,
                        "tenant_id": "t1",
                        "building_id": "b1",
                        "gateway_id": "gw-1",
                        "connector_id": "metasys",
                        "source": "metasys",
                        "source_point_id": "obj-1",
                        "metadata": {},
                        "enabled": True,
                    }
                ],
            )
        if method == "PATCH":
            return _mock_response(200, [])
        if method == "GET" and "point_current_state" in url:
            return _mock_response(
                200,
                [
                    {
                        "point_id": existing_id,
                        "normalized_quality": "GOOD",
                        "freshness_state": "LIVE",
                        "state": "LIVE",
                    }
                ],
            )
        return _mock_response(200, [])

    with patch.object(store._client, "request", side_effect=side_effect):
        p1 = store.upsert_raw_point(
            {
                "tenant_id": "t1",
                "building_id": "b1",
                "gateway_id": "gw-1",
                "connector_id": "metasys",
                "source_point_id": "obj-1",
            }
        )
        p2 = store.upsert_raw_point(
            {
                "tenant_id": "t1",
                "building_id": "b1",
                "gateway_id": "gw-1",
                "connector_id": "metasys",
                "source_point_id": "obj-1",
            }
        )
    assert p1["id"] == existing_id
    assert p2["id"] == existing_id


def test_event_idempotency(store):
    with patch.object(store._client, "request") as req:
        req.side_effect = [
            _mock_response(200, [{"event_id": "ev-1"}]),
            _mock_response(200, []),
        ]
        assert store.is_event_processed("ev-1") is True
        store.mark_event_processed(
            event_id="ev-1",
            tenant_id="t1",
            building_id="b1",
            gateway_id="gw-1",
        )
        post_call = req.call_args_list[-1]
        assert post_call[0][0] == "POST"
        assert "telemetry_events" in post_call[0][1]
        assert "ignore-duplicates" in post_call[1]["headers"]["Prefer"]


def test_update_current_state_three_timestamps(store):
    point_id = "22222222-2222-2222-2222-222222222222"
    source_ts = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)
    edge_ts = datetime(2026, 8, 29, 10, 0, 1, tzinfo=timezone.utc)
    cloud_ts = datetime(2026, 8, 29, 10, 0, 2, tzinfo=timezone.utc)

    with patch.object(store._client, "request") as req:
        req.side_effect = [
            _mock_response(200, []),
            _mock_response(
                200,
                [
                    {
                        "point_id": point_id,
                        "last_value": 21.0,
                        "last_source_timestamp": source_ts.isoformat(),
                        "last_edge_received_at": edge_ts.isoformat(),
                        "last_cloud_received_at": cloud_ts.isoformat(),
                        "normalized_quality": "GOOD",
                        "freshness_state": "LIVE",
                        "state": "LIVE",
                    }
                ],
            ),
        ]
        state = store.update_current_state(
            point_id=point_id,
            value=21.0,
            source_timestamp=source_ts,
            edge_received_at=edge_ts,
            cloud_received_at=cloud_ts,
            source_quality="good",
            normalized_quality="GOOD",
            expected_interval_seconds=30,
        )
    assert state["last_source_timestamp"].startswith("2026-08-29T10:00:00")
    assert state["last_edge_received_at"].startswith("2026-08-29T10:00:01")
    assert state["last_cloud_received_at"].startswith("2026-08-29T10:00:02")
