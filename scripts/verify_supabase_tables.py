#!/usr/bin/env python3
"""Verify Supabase tables and sync_bms_alert RPC."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://arddnpiluxrkndzzdpfi.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY", ""))
ALERT_SECRET = os.getenv("ALERT_WEBHOOK_SECRET", "")

MIGRATIONS = [
    Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "001_building_alerts.sql",
    Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "002_bms_connections.sql",
    Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "003_alert_acknowledge.sql",
    Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "004_sync_bms_alert_rpc.sql",
]

TABLES = ["building_alerts", "bms_connections"]


def headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def table_exists(table: str) -> bool:
    try:
        response = httpx.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=headers(),
            params={"select": "id", "limit": "1"},
            timeout=10.0,
        )
        return response.status_code == 200
    except Exception:
        return False


def rpc_exists() -> bool:
    if not ALERT_SECRET:
        print("sync_bms_alert RPC: SKIP (set ALERT_WEBHOOK_SECRET to test)")
        return True
    try:
        response = httpx.post(
            f"{SUPABASE_URL}/rest/v1/rpc/sync_bms_alert",
            headers={**headers(), "Content-Type": "application/json"},
            json={
                "p_secret": ALERT_SECRET,
                "p_alert": {
                    "id": "verify-rpc-check",
                    "building_id": "burj-khalifa-01",
                    "severity": "info",
                    "title": "RPC verify",
                    "message": "verify script",
                    "acknowledged": True,
                },
            },
            timeout=10.0,
        )
        ok = response.status_code == 200
        print(f"sync_bms_alert RPC: {'OK' if ok else 'MISSING'} (HTTP {response.status_code})")
        return ok
    except Exception as exc:
        print(f"sync_bms_alert RPC: FAIL ({exc})")
        return False


def main() -> int:
    if not SUPABASE_KEY or SUPABASE_KEY.startswith("your-"):
        print("Set SUPABASE_KEY or VITE_SUPABASE_PUBLISHABLE_KEY")
        return 1

    ok = True
    for table in TABLES:
        exists = table_exists(table)
        print(f"{table}: {'OK' if exists else 'MISSING'}")
        ok = ok and exists

    ok = ok and rpc_exists()

    if not ok:
        print("\nApply these SQL files in Supabase SQL editor:")
        for path in MIGRATIONS:
            if path.exists():
                print(f"  - {path.name}")
        return 1

    print("All required Supabase tables and RPC are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
