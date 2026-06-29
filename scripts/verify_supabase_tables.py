#!/usr/bin/env python3
"""Verify Supabase tables via REST and print migration status."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://arddnpiluxrkndzzdpfi.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY", ""))

MIGRATIONS = [
    Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "001_building_alerts.sql",
    Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "002_bms_connections.sql",
    Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "003_alert_acknowledge.sql",
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


def main() -> int:
    if not SUPABASE_KEY or SUPABASE_KEY.startswith("your-"):
        print("Set SUPABASE_KEY or VITE_SUPABASE_PUBLISHABLE_KEY")
        return 1

    ok = True
    for table in TABLES:
        exists = table_exists(table)
        print(f"{table}: {'OK' if exists else 'MISSING'}")
        ok = ok and exists

    if not ok:
        print("\nApply these SQL files in Supabase SQL editor (Lovable Cloud → Database):")
        for path in MIGRATIONS:
            if path.exists():
                print(f"  - {path.name}")
        return 1

    print("All required Supabase tables are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
