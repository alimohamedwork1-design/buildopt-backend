"""Deterministic, offline protocol-failure fixtures for lab regression testing.

This module does not open TCP sockets, read real buildings, import any OEM
drivers or write to controllers. Passing the lab is NOT protocol certification.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from typing import Any

PROTOCOLS = ("bacnet_ip", "modbus_tcp", "mqtt", "opc_ua", "rest")
SCENARIOS = (
    "healthy", "missing_value", "stale_timestamp", "clock_skew",
    "duplicate_event", "packet_loss", "invalid_unit", "offline",
)
REFERENCE_CLOCK = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
SAMPLES_PER_RUN = 12
ALLOWED_UNITS = {"°C", "kW", "%", "bar", "m3/h"}


def generate_fixture(
    protocol: str, scenario: str, *, clock: datetime = REFERENCE_CLOCK
) -> dict[str, Any]:
    if protocol not in PROTOCOLS:
        raise ValueError("Unsupported illustrative protocol")
    if scenario not in SCENARIOS:
        raise ValueError("Unsupported fault scenario")
    if clock.tzinfo is None:
        raise ValueError("Clock must be UTC-aware")
    rows = []
    for n in range(SAMPLES_PER_RUN):
        measured = clock - timedelta(minutes=SAMPLES_PER_RUN - n)
        received = measured + timedelta(seconds=2)
        processed = received + timedelta(seconds=1)
        rows.append(
            {
                "event_id": f"SIM-{protocol}-{n:03}",
                "point_id": "DEMO_CHILLER_01.SUPPLY_T",
                "source": f"synthetic_{protocol}",
                "value": round(6.5 + (n % 4) * 0.15, 3),
                "unit": "°C",
                "source_timestamp": measured.isoformat(),
                "edge_received_at": received.isoformat(),
                "processed_at": processed.isoformat(),
                "source_quality": "GOOD",
            }
        )
    if scenario == "missing_value":
        rows[4]["value"] = None
    elif scenario == "stale_timestamp":
        rows[4]["source_timestamp"] = (clock - timedelta(hours=2)).isoformat()
    elif scenario == "clock_skew":
        rows[4]["source_timestamp"] = (clock + timedelta(minutes=8)).isoformat()
    elif scenario == "duplicate_event":
        rows.insert(5, dict(rows[4]))
    elif scenario == "packet_loss":
        rows = [r for i, r in enumerate(rows) if i not in (4, 5, 6, 7)]
    elif scenario == "invalid_unit":
        rows[4]["unit"] = "unmapped"
    elif scenario == "offline":
        rows = []
    return {
        "protocol": protocol,
        "scenario": scenario,
        "simulated": True,
        "real_site": False,
        "writeback_enabled": False,
        "device_connections_attempted": 0,
        "clock": clock.isoformat(),
        "expected_samples": SAMPLES_PER_RUN,
        "samples": rows,
    }


def evaluate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    if fixture.get("simulated") is not True:
        raise ValueError("Evaluation is restricted to synthetic fixtures")
    now = datetime.fromisoformat(fixture["clock"])
    if now.tzinfo is None:
        raise ValueError("Clock must be UTC-aware")
    seen = set()
    issues: list[dict[str, str]] = []
    good = 0
    for row in fixture["samples"]:
        event = row["event_id"]
        reason = ""
        if event in seen:
            reason = "duplicate_event"
        seen.add(event)
        try:
            source = datetime.fromisoformat(row["source_timestamp"])
            received = datetime.fromisoformat(row["edge_received_at"])
            processed = datetime.fromisoformat(row["processed_at"])
            if any(t.tzinfo is None for t in (source, received, processed)):
                reason = "invalid_timestamp"
            elif not (source <= received <= processed <= now + timedelta(minutes=1)):
                reason = "clock_skew"
            elif now - source > timedelta(minutes=30):
                reason = "stale_timestamp"
        except (ValueError, TypeError, KeyError):
            reason = "invalid_timestamp"
        if row.get("value") is None:
            reason = "missing_value"
        if row.get("unit") not in ALLOWED_UNITS:
            reason = "invalid_unit"
        if row.get("source_quality") != "GOOD" and not reason:
            reason = "source_quality_not_good"
        if reason:
            issues.append({"event_id": str(event), "reason": reason})
        else:
            good += 1
    # Expected transmissions are fixed; duplicates cannot boost completeness.
    unique = len(seen)
    expected = int(fixture["expected_samples"])
    if unique < expected:
        issues.append({"event_id": "-", "reason": "packet_loss_or_outage"})
    if len(fixture["samples"]) == 0:
        issues.append({"event_id": "-", "reason": "connector_offline"})
    passed = len(issues) == 0 and good == expected
    return {
        "protocol": fixture["protocol"],
        "scenario": fixture["scenario"],
        "simulated": True,
        "field_validated": False,
        "lab_regression_passed": passed,
        "expected_samples": expected,
        "received_samples": len(fixture["samples"]),
        "unique_samples": unique,
        "quality_accepted": good,
        "completeness": round(min(1.0, unique / expected), 3) if expected else 0.0,
        "issues": issues,
        "writeback_enabled": False,
        "device_connections_attempted": 0,
        "interpretation": (
            "A synthetic fixture regression, not evidence of a real protocol "
            "connection, certified adapter, usable site telemetry or savings."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="BuildOpt offline synthetic protocol lab")
    parser.add_argument("--protocol", choices=PROTOCOLS, default="bacnet_ip")
    parser.add_argument("--scenario", choices=SCENARIOS, default="healthy")
    args = parser.parse_args()
    result = evaluate_fixture(generate_fixture(args.protocol, args.scenario))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
