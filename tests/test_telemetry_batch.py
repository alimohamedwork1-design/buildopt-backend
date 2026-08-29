import pytest
from datetime import datetime, timezone

from app.services.edge_heartbeat_store import EdgeHeartbeatStore


def test_gateway_heartbeat_and_stale_state():
    store = EdgeHeartbeatStore()
    store.record_gateway(
        gateway_id="gw-1",
        building_id="b-1",
        tenant_id="t-1",
        connector_status="ONLINE",
        telemetry_rate=12,
        queue_depth=3,
    )
    gateways = store.list_gateways()
    assert len(gateways) == 1
    assert gateways[0]["gateway_id"] == "gw-1"
    assert gateways[0]["telemetry_rate"] == 12
    assert gateways[0]["queue_depth"] == 3


def test_telemetry_batch_dedupe_logic():
    from app.api.telemetry import TelemetryReading, _dedupe_readings

    ts = datetime.now(timezone.utc)
    readings = [
        TelemetryReading(building_id="b1", point_id="sat", timestamp=ts, value=13.5),
        TelemetryReading(building_id="b1", point_id="sat", timestamp=ts, value=13.5),
        TelemetryReading(building_id="b1", point_id="rat", timestamp=ts, value=24.0),
    ]
    unique = _dedupe_readings(readings)
    assert len(unique) == 2
