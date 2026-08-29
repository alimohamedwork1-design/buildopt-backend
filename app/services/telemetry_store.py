"""SQLite-backed telemetry registry — gateways, raw points, current state, idempotency."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services.freshness_engine import apply_quality_state, compute_freshness

logger = logging.getLogger("buildopt.telemetry.store")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class TelemetryStore:
    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            create table if not exists gateways (
                gateway_id text primary key,
                tenant_id text not null,
                building_id text not null,
                connector_id text not null default 'metasys',
                enabled integer not null default 1,
                created_at text not null,
                updated_at text not null
            );

            create table if not exists raw_points (
                id text primary key,
                tenant_id text not null,
                building_id text not null,
                gateway_id text not null,
                connector_id text not null,
                source text not null,
                source_point_id text not null,
                source_name text,
                source_path text,
                source_type text,
                raw_unit text,
                metadata text not null default '{}',
                discovered_at text not null,
                last_seen_at text not null,
                created_at text not null,
                updated_at text not null,
                enabled integer not null default 1,
                expected_interval_seconds integer not null default 30,
                unique (tenant_id, connector_id, source_point_id)
            );

            create table if not exists point_current_state (
                point_id text primary key,
                last_value real,
                last_value_text text,
                last_source_timestamp text,
                last_edge_received_at text,
                last_cloud_received_at text,
                source_quality text,
                normalized_quality text not null default 'NO_DATA',
                freshness_seconds integer,
                expected_interval_seconds integer not null default 30,
                freshness_state text not null default 'NO_DATA',
                state text not null default 'NO_DATA',
                updated_at text not null
            );

            create table if not exists telemetry_events (
                event_id text primary key,
                tenant_id text not null,
                building_id text not null,
                gateway_id text not null,
                processed_at text not null
            );

            create index if not exists raw_points_building_idx on raw_points(building_id);
            create index if not exists raw_points_gateway_idx on raw_points(gateway_id);
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---- Gateways ----

    def register_gateway(
        self,
        *,
        gateway_id: str,
        tenant_id: str,
        building_id: str,
        connector_id: str,
    ) -> Dict[str, Any]:
        now = _iso(_utcnow())
        existing = self.get_gateway(gateway_id)
        if existing:
            if existing["tenant_id"] != tenant_id or existing["building_id"] != building_id:
                raise PermissionError("gateway_identity_mismatch")
            return existing
        self._conn.execute(
            """
            insert into gateways (gateway_id, tenant_id, building_id, connector_id, enabled, created_at, updated_at)
            values (?, ?, ?, ?, 1, ?, ?)
            """,
            (gateway_id, tenant_id, building_id, connector_id, now, now),
        )
        self._conn.commit()
        return self.get_gateway(gateway_id) or {}

    def get_gateway(self, gateway_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute("select * from gateways where gateway_id=?", (gateway_id,)).fetchone()
        return dict(row) if row else None

    def validate_gateway_scope(
        self,
        *,
        gateway_id: str,
        tenant_id: str,
        building_id: str,
        connector_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        gw = self.register_gateway(
            gateway_id=gateway_id,
            tenant_id=tenant_id,
            building_id=building_id,
            connector_id=connector_id or "metasys",
        )
        if gw["tenant_id"] != tenant_id:
            raise PermissionError("cross_tenant_rejected")
        if gw["building_id"] != building_id:
            raise PermissionError("cross_building_rejected")
        return gw

    # ---- Raw points ----

    def upsert_raw_point(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = _iso(_utcnow())
        tenant_id = payload["tenant_id"]
        connector_id = payload["connector_id"]
        source_point_id = payload["source_point_id"]
        existing = self._conn.execute(
            """
            select * from raw_points
            where tenant_id=? and connector_id=? and source_point_id=?
            """,
            (tenant_id, connector_id, source_point_id),
        ).fetchone()

        metadata = json.dumps(payload.get("metadata") or {})
        if existing:
            point_id = existing["id"]
            self._conn.execute(
                """
                update raw_points set
                    source_name=?, source_path=?, source_type=?, raw_unit=?,
                    metadata=?, last_seen_at=?, updated_at=?,
                    source=?, gateway_id=?, building_id=?
                where id=?
                """,
                (
                    payload.get("source_name"),
                    payload.get("source_path"),
                    payload.get("source_type"),
                    payload.get("raw_unit"),
                    metadata,
                    now,
                    now,
                    payload.get("source", "metasys"),
                    payload["gateway_id"],
                    payload["building_id"],
                    point_id,
                ),
            )
        else:
            point_id = str(uuid.uuid4())
            self._conn.execute(
                """
                insert into raw_points (
                    id, tenant_id, building_id, gateway_id, connector_id, source,
                    source_point_id, source_name, source_path, source_type, raw_unit,
                    metadata, discovered_at, last_seen_at, created_at, updated_at, enabled,
                    expected_interval_seconds
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    point_id,
                    tenant_id,
                    payload["building_id"],
                    payload["gateway_id"],
                    connector_id,
                    payload.get("source", "metasys"),
                    source_point_id,
                    payload.get("source_name"),
                    payload.get("source_path"),
                    payload.get("source_type"),
                    payload.get("raw_unit"),
                    metadata,
                    now,
                    now,
                    now,
                    now,
                    int(payload.get("expected_interval_seconds") or 30),
                ),
            )
            self._conn.execute(
                """
                insert into point_current_state (
                    point_id, normalized_quality, freshness_state, state,
                    expected_interval_seconds, updated_at
                ) values (?, 'NO_DATA', 'NO_DATA', 'NO_DATA', ?, ?)
                """,
                (point_id, int(payload.get("expected_interval_seconds") or 30), now),
            )
        self._conn.commit()
        return self.get_point(point_id) or {}

    def get_point(self, point_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute("select * from raw_points where id=?", (point_id,)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["metadata"] = json.loads(out.get("metadata") or "{}")
        state = self.get_current_state(point_id)
        if state:
            out["current"] = state
        return out

    def find_point_by_source(
        self,
        *,
        tenant_id: str,
        connector_id: str,
        source_point_id: str,
    ) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            """
            select * from raw_points
            where tenant_id=? and connector_id=? and source_point_id=?
            """,
            (tenant_id, connector_id, source_point_id),
        ).fetchone()
        if not row:
            return None
        return self.get_point(row["id"])

    def list_points(
        self,
        *,
        tenant_id: Optional[str] = None,
        building_id: Optional[str] = None,
        gateway_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        clauses: List[str] = []
        params: List[Any] = []
        if tenant_id:
            clauses.append("tenant_id=?")
            params.append(tenant_id)
        if building_id:
            clauses.append("building_id=?")
            params.append(building_id)
        if gateway_id:
            clauses.append("gateway_id=?")
            params.append(gateway_id)
        where = f"where {' and '.join(clauses)}" if clauses else ""
        total = self._conn.execute(f"select count(*) from raw_points {where}", params).fetchone()[0]
        rows = self._conn.execute(
            f"select id from raw_points {where} order by last_seen_at desc limit ? offset ?",
            (*params, limit, offset),
        ).fetchall()
        return [self.get_point(r["id"]) for r in rows if self.get_point(r["id"])], int(total)

    # ---- Current state ----

    def get_current_state(self, point_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute("select * from point_current_state where point_id=?", (point_id,)).fetchone()
        return dict(row) if row else None

    def update_current_state(
        self,
        *,
        point_id: str,
        value: Any,
        source_timestamp: Optional[datetime],
        edge_received_at: Optional[datetime],
        cloud_received_at: datetime,
        source_quality: str,
        normalized_quality: str,
        expected_interval_seconds: int,
    ) -> Dict[str, Any]:
        freshness = compute_freshness(
            last_cloud_received_at=cloud_received_at,
            expected_interval_seconds=expected_interval_seconds,
        )
        state = apply_quality_state(freshness["state"], normalized_quality)
        numeric = float(value) if isinstance(value, (int, float)) else None
        text = None if numeric is not None else (str(value) if value is not None else None)
        now = _iso(_utcnow())
        self._conn.execute(
            """
            insert into point_current_state (
                point_id, last_value, last_value_text, last_source_timestamp,
                last_edge_received_at, last_cloud_received_at, source_quality,
                normalized_quality, freshness_seconds, expected_interval_seconds,
                freshness_state, state, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(point_id) do update set
                last_value=excluded.last_value,
                last_value_text=excluded.last_value_text,
                last_source_timestamp=excluded.last_source_timestamp,
                last_edge_received_at=excluded.last_edge_received_at,
                last_cloud_received_at=excluded.last_cloud_received_at,
                source_quality=excluded.source_quality,
                normalized_quality=excluded.normalized_quality,
                freshness_seconds=excluded.freshness_seconds,
                expected_interval_seconds=excluded.expected_interval_seconds,
                freshness_state=excluded.freshness_state,
                state=excluded.state,
                updated_at=excluded.updated_at
            """,
            (
                point_id,
                numeric,
                text,
                _iso(source_timestamp),
                _iso(edge_received_at),
                _iso(cloud_received_at),
                source_quality,
                normalized_quality,
                freshness["freshness_seconds"],
                expected_interval_seconds,
                freshness["freshness_state"],
                state,
                now,
            ),
        )
        self._conn.commit()
        return self.get_current_state(point_id) or {}

    def list_building_current(
        self,
        building_id: str,
        *,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses = ["rp.building_id=?"]
        params: List[Any] = [building_id]
        if tenant_id:
            clauses.append("rp.tenant_id=?")
            params.append(tenant_id)
        rows = self._conn.execute(
            f"""
            select rp.*, pcs.*
            from raw_points rp
            left join point_current_state pcs on pcs.point_id = rp.id
            where {' and '.join(clauses)}
            order by rp.source_name asc
            """,
            params,
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            point = self.get_point(row["id"])
            if point:
                out.append(point)
        return out

    # ---- Idempotency ----

    def is_event_processed(self, event_id: str) -> bool:
        row = self._conn.execute(
            "select 1 from telemetry_events where event_id=?", (event_id,)
        ).fetchone()
        return row is not None

    def mark_event_processed(
        self,
        *,
        event_id: str,
        tenant_id: str,
        building_id: str,
        gateway_id: str,
    ) -> None:
        self._conn.execute(
            """
            insert or ignore into telemetry_events (event_id, tenant_id, building_id, gateway_id, processed_at)
            values (?, ?, ?, ?, ?)
            """,
            (event_id, tenant_id, building_id, gateway_id, _iso(_utcnow())),
        )
        self._conn.commit()


_store: Optional[Any] = None
_store_status: Dict[str, Any] = {}


class TelemetryStoreUnavailableError(RuntimeError):
    """Raised when production requires durable Supabase registry but it is not configured."""


def _placeholder_key(key: str) -> bool:
    return not key or key.startswith("your-")


def _is_production_live(settings) -> bool:
    if settings.app_env == "test":
        return False
    return not settings.demo_mode and settings.app_env.lower() in ("production", "prod")


def resolve_telemetry_backend(settings) -> Tuple[str, Optional[str]]:
    """Return (backend_kind, error_message). backend_kind: memory|sqlite|supabase|unavailable."""
    backend = (settings.telemetry_store_backend or "auto").lower()

    if settings.app_env == "test" or backend == "memory":
        return "memory", None

    if backend == "sqlite":
        return "sqlite", None

    url_ok = bool(settings.supabase_url) and not settings.supabase_url.startswith("https://your-")
    service_ok = bool(settings.supabase_service_key) and not _placeholder_key(
        settings.supabase_service_key
    )

    if backend == "supabase":
        if not url_ok or not service_ok:
            return (
                "unavailable",
                "TELEMETRY_STORE_BACKEND=supabase requires SUPABASE_URL and SUPABASE_SERVICE_KEY",
            )
        return "supabase", None

    if url_ok and service_ok:
        return "supabase", None

    if _is_production_live(settings):
        return (
            "unavailable",
            "Durable telemetry registry required in production (DEMO_MODE=false). "
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY.",
        )

    return "sqlite", None


def get_telemetry_store_status() -> Dict[str, Any]:
    """Safe telemetry registry status for health endpoints — never includes secrets."""
    from app.config import get_settings

    settings = get_settings()
    resolved, error = resolve_telemetry_backend(settings)

    if _store is not None:
        active_path = getattr(_store, "db_path", "unknown")
        if active_path == "supabase":
            active = "supabase"
        elif active_path == ":memory:":
            active = "memory"
        else:
            active = "sqlite"
    else:
        active = resolved if resolved != "unavailable" else "none"

    required = _is_production_live(settings)
    if resolved == "unavailable":
        status = "not_configured"
    elif active == "supabase":
        status = "connected"
    elif active == "sqlite" and required:
        status = "degraded"
    elif active in ("sqlite", "memory"):
        status = "connected"
    else:
        status = "unknown"

    durable = active == "supabase"
    return {
        "backend": active,
        "durable": durable,
        "required": required,
        "status": status,
        "message": error,
    }


def get_telemetry_store() -> Any:
    global _store, _store_status
    if _store is None:
        import os

        from app.config import get_settings

        settings = get_settings()
        resolved, error = resolve_telemetry_backend(settings)

        if resolved == "unavailable":
            _store_status = {
                "backend": "none",
                "durable": False,
                "required": _is_production_live(settings),
                "status": "not_configured",
                "message": error,
            }
            raise TelemetryStoreUnavailableError(error or "telemetry_store_unavailable")

        if resolved == "memory":
            _store = TelemetryStore(":memory:")
            logger.info("Telemetry registry: in-memory (test)")
        elif resolved == "sqlite":
            db_path = os.getenv("TELEMETRY_DB_PATH", "data/telemetry.db")
            _store = TelemetryStore(db_path)
            if _is_production_live(settings):
                logger.warning(
                    "Telemetry registry: SQLite (%s) — explicit TELEMETRY_STORE_BACKEND=sqlite in production",
                    db_path,
                )
            else:
                logger.info("Telemetry registry: SQLite (%s)", db_path)
        elif resolved == "supabase":
            from app.services.supabase_telemetry_store import SupabaseTelemetryStore

            _store = SupabaseTelemetryStore(settings.supabase_url, settings.supabase_service_key)
            logger.info("Telemetry registry: Supabase PostgREST (durable)")
        else:
            db_path = os.getenv("TELEMETRY_DB_PATH", "data/telemetry.db")
            _store = TelemetryStore(db_path)

        _store_status = get_telemetry_store_status()
    return _store


def reset_telemetry_store(store: Optional[Any] = None) -> None:
    global _store, _store_status
    if _store and getattr(_store, "db_path", None) not in (":memory:", "supabase"):
        _store.close()
    elif _store and getattr(_store, "db_path", None) == "supabase":
        _store.close()
    _store = store
    _store_status = get_telemetry_store_status() if store is not None else {}
