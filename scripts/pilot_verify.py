#!/usr/bin/env python3
"""Pilot acceptance verification — automated checks (no fake telemetry)."""

from __future__ import annotations

import sys
import urllib.request
import json

API = "https://buildopt-backend-production.up.railway.app/api/v1"
CHECKS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))


def get(path: str) -> tuple[int, dict]:
    try:
        req = urllib.request.Request(f"{API}{path}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else "{}"
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"raw": body}
    except Exception as exc:
        return 0, {"error": str(exc)}


def main() -> int:
    code, health = get("/health")
    check("Backend /health", code == 200, health.get("status", ""))

    code, conn = get("/health/connections")
    check("demo_mode=false", conn.get("demo_mode") is False)
    check("Influx connected", conn.get("influxdb") == "connected")
    check("Durable telemetry", conn.get("telemetry_store", {}).get("durable") is True)
    check("Ingest auth enabled", conn.get("ingest_api") is True)

    code, _ = get("/semantic/buildings/demo/review-queue")
    check("Semantic review route", code in (401, 403), f"HTTP {code}")

    code, _ = get("/fdd/buildings/demo/faults")
    check("FDD faults route", code in (401, 403), f"HTTP {code}")

    code, _ = get("/reports/writeback/status")
    check("Writeback status route", code in (401, 403, 200), f"HTTP {code}")

    check("Real Metasys connection", False, "BLOCKED_REAL_SITE")
    check("Real discovery run", False, "BLOCKED_REAL_SITE")
    check("7-day live history validation", False, "BLOCKED_REAL_SITE")

    failed = sum(1 for _, ok, _ in CHECKS if not ok)
    blocked = sum(1 for _, ok, d in CHECKS if not ok and "BLOCKED" in d)
    print(f"\nTotal: {len(CHECKS)} checks, {failed} failed ({blocked} blocked real-site)")
    return 0 if failed == blocked else 1


if __name__ == "__main__":
    sys.exit(main())
