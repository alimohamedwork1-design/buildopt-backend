import pytest
from datetime import datetime, timezone

from app.services.edge_heartbeat_store import EdgeHeartbeatStore
from app.services.telemetry_pipeline import stable_event_id


def test_gateway_heartbeat_and_stale_state():
    store = EdgeHeartbeatStore()
    store.record_gateway(
        gateway_id="gw-1",
        building_id="b-1",
        tenant_id="t-1",
        connector_status="ONLINE",
        telemetry_rate=12,
        queue_depth=3,
        clock_drift_seconds=5,
    )
    gateways = store.list_gateways()
    assert len(gateways) == 1
    assert gateways[0]["gateway_id"] == "gw-1"
    assert gateways[0]["telemetry_rate"] == 12
    assert gateways[0]["queue_depth"] == 3


def test_stable_event_id_dedupe():
    ts = datetime.now(timezone.utc)
    a = stable_event_id(
        gateway_id="gw",
        building_id="b1",
        connector_id="metasys",
        source_point_id="sat",
        source_timestamp=ts,
        edge_received_at=ts,
        value=13.5,
    )
    b = stable_event_id(
        gateway_id="gw",
        building_id="b1",
        connector_id="metasys",
        source_point_id="sat",
        source_timestamp=ts,
        edge_received_at=ts,
        value=13.5,
    )
    assert a == b
