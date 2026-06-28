#!/usr/bin/env python3
"""Apply Supabase migration when SUPABASE_SERVICE_KEY is set."""

from __future__ import annotations

import os
import sys
from pathlib import Path

MIGRATION = Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "001_building_alerts.sql"


def main() -> int:
    url = os.getenv("SUPABASE_URL", "https://arddnpiluxrkndzzdpfi.supabase.co")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not key or key.startswith("your-"):
        print("Set SUPABASE_SERVICE_KEY (service_role) from Supabase → Settings → API")
        print("Then run: SUPABASE_SERVICE_KEY=... python scripts/apply_supabase_migration.py")
        return 1

    try:
        from supabase import create_client
    except ImportError:
        print("pip install supabase")
        return 1

    sql = MIGRATION.read_text(encoding="utf-8")
    client = create_client(url, key)

    # Supabase Python client uses postgrest; run DDL via rpc if available
    try:
        client.postgrest.rpc("exec_sql", {"query": sql}).execute()
        print("Migration applied via exec_sql RPC")
        return 0
    except Exception:
        pass

    # Fallback: create building_alerts via REST if table missing (insert probe)
    try:
        client.table("building_alerts").select("id").limit(1).execute()
        print("building_alerts table already exists")
        return 0
    except Exception as e:
        print(f"Cannot auto-apply DDL without Supabase SQL editor: {e}")
        print(f"Paste this file manually in Supabase SQL editor:\n  {MIGRATION}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
