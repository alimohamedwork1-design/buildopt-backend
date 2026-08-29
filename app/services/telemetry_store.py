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

            create table if not exists gateway_tokens (
                token_id text primary key,
                gateway_id text not null,
                token_hash text not null unique,
                label text,
                created_at text not null,
                revoked_at text,
                expires_at text
            );
            create index if not exists gateway_tokens_gateway_idx on gateway_tokens(gateway_id);

            create table if not exists semantic_audit_log (
                audit_id text primary key,
                point_id text,
                building_id text not null,
                tenant_id text,
                gateway_id text,
                source_point_id text,
                action text not null,
                previous_state text not null default '{}',
                new_state text not null default '{}',
                actor_user_id text,
                actor_email text,
                comment text,
                confidence real,
                created_at text not null
            );
            create index if not exists semantic_audit_building_idx on semantic_audit_log(building_id);

            create table if not exists collection_config_versions (
                config_version text primary key,
                building_id text not null,
                gateway_id text,
                tenant_id text,
                mapping_revision integer not null default 1,
                point_count integer not null default 0,
                approved_count integer not null default 0,
                status text not null default 'DRAFT',
                config_payload text not null default '{}',
                created_at text not null,
                activated_at text
            );
            create index if not exists collection_config_building_idx on collection_config_versions(building_id);

            create table if not exists fdd_faults (
                fault_id text primary key,
                rule_id text not null,
                tenant_id text,
                building_id text not null,
                equipment_id text not null,
                equipment_type text not null default 'AHU',
                severity text not null default 'warning',
                status text not null default 'DETECTED',
                confidence real not null default 0.5,
                data_quality_score real,
                input_coverage real,
                evidence text not null default '{}',
                source_points text not null default '[]',
                observed_values text not null default '{}',
                reason text,
                recommended_next_check text,
                first_seen text not null,
                last_seen text not null,
                detected_at text not null,
                resolved_at text,
                created_at text not null,
                updated_at text not null
            );
            create index if not exists fdd_faults_building_idx on fdd_faults(building_id, status);

            create table if not exists fdd_fault_audit (
                audit_id text primary key,
                fault_id text not null,
                action text not null,
                previous_status text,
                new_status text,
                actor_user_id text,
                comment text,
                created_at text not null
            );

            create table if not exists recommendations (
                id text primary key,
                tenant_id text,
                building_id text not null,
                equipment_id text,
                fault_id text,
                rec_type text not null default 'fdd_action',
                title text not null,
                description text not null default '',
                state text not null default 'DETECTED',
                severity text not null default 'warning',
                owner text,
                evidence text not null default '{}',
                recommended_action text,
                expected_impact text not null default '{}',
                confidence real,
                risk text,
                comfort_impact text,
                verification_plan text,
                expected_saving_aed real,
                verified_saving_aed real,
                approved_by text,
                implemented_at text,
                verified_at text,
                work_order_id text,
                created_at text not null,
                updated_at text not null
            );
            create index if not exists recommendations_building_idx on recommendations(building_id, state);

            create table if not exists recommendation_audit (
                audit_id text primary key,
                recommendation_id text not null,
                action text not null,
                previous_state text,
                new_state text,
                actor_user_id text,
                comment text,
                created_at text not null
            );

            create table if not exists savings_opportunities (
                id text primary key,
                tenant_id text,
                building_id text not null,
                recommendation_id text,
                title text not null,
                state text not null default 'POTENTIAL',
                baseline_kwh real not null default 0,
                expected_kwh real not null default 0,
                actual_kwh real,
                avoided_kwh real,
                tariff_aed_per_kwh real not null default 0.38,
                expected_saving_aed real not null default 0,
                verified_saving_aed real,
                confidence real not null default 0.5,
                methodology text not null default 'baseline_comparison',
                data_coverage_pct real not null default 0,
                notes text,
                measurement_period_start text,
                measurement_period_end text,
                implementation_date text,
                before_energy_kwh real,
                after_energy_kwh real,
                normalized_baseline_kwh real,
                weather_context text not null default '{}',
                schedule_context text not null default '{}',
                energy_saved_kwh real,
                cost_saved real,
                currency text not null default 'AED',
                uncertainty real,
                verification_status text,
                excluded_periods text not null default '[]',
                calculation_version text not null default 'mv_v1',
                created_at text not null,
                updated_at text not null
            );
            create index if not exists savings_building_idx on savings_opportunities(building_id, state);

            create table if not exists savings_audit (
                audit_id text primary key,
                savings_id text not null,
                action text not null,
                previous_state text,
                new_state text,
                actor_user_id text,
                comment text,
                created_at text not null
            );
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

    def update_point_metadata(self, point_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        now = _iso(_utcnow())
        self._conn.execute(
            "update raw_points set metadata=?, updated_at=? where id=?",
            (json.dumps(metadata or {}), now, point_id),
        )
        self._conn.commit()
        return self.get_point(point_id) or {}

    # ---- Semantic audit ----

    def insert_semantic_audit(
        self,
        *,
        audit_id: str,
        point_id: Optional[str],
        building_id: str,
        tenant_id: Optional[str],
        gateway_id: Optional[str],
        source_point_id: Optional[str],
        action: str,
        previous_state: Dict[str, Any],
        new_state: Dict[str, Any],
        actor_user_id: Optional[str],
        actor_email: Optional[str],
        comment: Optional[str],
        confidence: Optional[float],
    ) -> Dict[str, Any]:
        now = _iso(_utcnow())
        self._conn.execute(
            """
            insert into semantic_audit_log (
                audit_id, point_id, building_id, tenant_id, gateway_id, source_point_id,
                action, previous_state, new_state, actor_user_id, actor_email, comment, confidence, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id, point_id, building_id, tenant_id, gateway_id, source_point_id,
                action, json.dumps(previous_state or {}), json.dumps(new_state or {}),
                actor_user_id, actor_email, comment, confidence, now,
            ),
        )
        self._conn.commit()
        return {"audit_id": audit_id, "action": action, "created_at": now}

    def list_semantic_audit(
        self,
        *,
        building_id: Optional[str] = None,
        point_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if point_id:
            rows = self._conn.execute(
                "select * from semantic_audit_log where point_id=? order by created_at desc limit ?",
                (point_id, limit),
            ).fetchall()
        elif building_id:
            rows = self._conn.execute(
                "select * from semantic_audit_log where building_id=? order by created_at desc limit ?",
                (building_id, limit),
            ).fetchall()
        else:
            return []
        out = []
        for row in rows:
            d = dict(row)
            d["previous_state"] = json.loads(d.get("previous_state") or "{}")
            d["new_state"] = json.loads(d.get("new_state") or "{}")
            out.append(d)
        return out

    # ---- Collection config versions ----

    def next_mapping_revision(self, building_id: str, gateway_id: Optional[str]) -> int:
        clause = "building_id=?"
        params: List[Any] = [building_id]
        if gateway_id:
            clause += " and gateway_id=?"
            params.append(gateway_id)
        row = self._conn.execute(
            f"select max(mapping_revision) as rev from collection_config_versions where {clause}",
            params,
        ).fetchone()
        return int((row["rev"] or 0) + 1) if row else 1

    def supersede_active_config_versions(self, building_id: str, gateway_id: Optional[str]) -> None:
        clause = "building_id=? and status='ACTIVE'"
        params: List[Any] = [building_id]
        if gateway_id:
            clause += " and gateway_id=?"
            params.append(gateway_id)
        self._conn.execute(
            f"update collection_config_versions set status='SUPERSEDED' where {clause}",
            params,
        )

    def publish_active_config_version(
        self,
        *,
        config_version: str,
        building_id: str,
        gateway_id: Optional[str],
        tenant_id: Optional[str],
        mapping_revision: int,
        point_count: int,
        approved_count: int,
        config_payload: Dict[str, Any],
        activated_at: Optional[datetime],
    ) -> Dict[str, Any]:
        """Atomically supersede prior ACTIVE and insert new ACTIVE — single transaction."""
        now = _iso(_utcnow())
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            clause = "building_id=? and status='ACTIVE'"
            params: List[Any] = [building_id]
            if gateway_id:
                clause += " and gateway_id=?"
                params.append(gateway_id)
            self._conn.execute(
                f"update collection_config_versions set status='SUPERSEDED' where {clause}",
                params,
            )
            self._conn.execute(
                """
                insert into collection_config_versions (
                    config_version, building_id, gateway_id, tenant_id, mapping_revision,
                    point_count, approved_count, status, config_payload, created_at, activated_at
                ) values (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
                """,
                (
                    config_version, building_id, gateway_id, tenant_id, mapping_revision,
                    point_count, approved_count, json.dumps(config_payload or {}),
                    now, _iso(activated_at),
                ),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return {"config_version": config_version, "created_at": now, "status": "ACTIVE"}

    def insert_config_version(
        self,
        *,
        config_version: str,
        building_id: str,
        gateway_id: Optional[str],
        tenant_id: Optional[str],
        mapping_revision: int,
        point_count: int,
        approved_count: int,
        status: str,
        config_payload: Dict[str, Any],
        activated_at: Optional[datetime],
    ) -> Dict[str, Any]:
        now = _iso(_utcnow())
        self._conn.execute(
            """
            insert into collection_config_versions (
                config_version, building_id, gateway_id, tenant_id, mapping_revision,
                point_count, approved_count, status, config_payload, created_at, activated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                config_version, building_id, gateway_id, tenant_id, mapping_revision,
                point_count, approved_count, status, json.dumps(config_payload or {}),
                now, _iso(activated_at),
            ),
        )
        self._conn.commit()
        return {"config_version": config_version, "created_at": now, "status": status}

    def get_active_config_version(
        self, building_id: str, gateway_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        clause = "building_id=? and status='ACTIVE'"
        params: List[Any] = [building_id]
        if gateway_id:
            clause += " and gateway_id=?"
            params.append(gateway_id)
        row = self._conn.execute(
            f"select * from collection_config_versions where {clause} order by created_at desc limit 1",
            params,
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["config_payload"] = json.loads(d.get("config_payload") or "{}")
        return d

    def list_config_versions(self, building_id: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            """
            select config_version, building_id, gateway_id, mapping_revision, point_count,
                   approved_count, status, created_at, activated_at
            from collection_config_versions where building_id=? order by created_at desc limit ?
            """,
            (building_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- FDD faults ----

    def upsert_fdd_fault(self, fault: Dict[str, Any]) -> Dict[str, Any]:
        now = _iso(_utcnow())
        self._conn.execute(
            """
            insert into fdd_faults (
                fault_id, rule_id, tenant_id, building_id, equipment_id, equipment_type,
                severity, status, confidence, data_quality_score, input_coverage,
                evidence, source_points, observed_values, reason, recommended_next_check,
                first_seen, last_seen, detected_at, resolved_at, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(fault_id) do update set
                status=excluded.status, confidence=excluded.confidence,
                data_quality_score=excluded.data_quality_score, input_coverage=excluded.input_coverage,
                evidence=excluded.evidence, source_points=excluded.source_points,
                observed_values=excluded.observed_values, last_seen=excluded.last_seen,
                resolved_at=excluded.resolved_at, updated_at=excluded.updated_at
            """,
            (
                fault["fault_id"], fault["rule_id"], fault.get("tenant_id"), fault["building_id"],
                fault["equipment_id"], fault.get("equipment_type", "AHU"),
                fault.get("severity", "warning"), fault.get("status", "DETECTED"),
                fault.get("confidence", 0.5), fault.get("data_quality_score"), fault.get("input_coverage"),
                json.dumps(fault.get("evidence") or {}),
                json.dumps(fault.get("source_points") or []),
                json.dumps(fault.get("observed_values") or {}),
                fault.get("reason"), fault.get("recommended_next_check"),
                fault.get("first_seen", now), fault.get("last_seen", now),
                fault.get("detected_at", now), fault.get("resolved_at"),
                fault.get("created_at", now), now,
            ),
        )
        self._conn.commit()
        return self.get_fdd_fault(fault["fault_id"]) or fault

    def get_fdd_fault(self, fault_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute("select * from fdd_faults where fault_id=?", (fault_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ("evidence", "source_points", "observed_values"):
            if isinstance(d.get(key), str):
                d[key] = json.loads(d[key] or "{}") if key != "source_points" else json.loads(d[key] or "[]")
        return d

    def list_fdd_faults(
        self, building_id: str, *, active_only: bool = True, limit: int = 100
    ) -> List[Dict[str, Any]]:
        clause = "building_id=?"
        params: List[Any] = [building_id]
        if active_only:
            clause += " and status not in ('RESOLVED', 'CLOSED')"
        rows = self._conn.execute(
            f"select * from fdd_faults where {clause} order by last_seen desc limit ?",
            (*params, limit),
        ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            for key in ("evidence", "source_points", "observed_values"):
                if isinstance(d.get(key), str):
                    d[key] = json.loads(d[key] or ("{}" if key != "source_points" else "[]"))
            out.append(d)
        return out

    def insert_fdd_fault_audit(
        self,
        *,
        audit_id: str,
        fault_id: str,
        action: str,
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> None:
        self._conn.execute(
            """
            insert into fdd_fault_audit (
                audit_id, fault_id, action, previous_status, new_status, actor_user_id, comment, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (audit_id, fault_id, action, previous_status, new_status, actor_user_id, comment, _iso(_utcnow())),
        )
        self._conn.commit()

    # ---- Recommendations ----

    @staticmethod
    def _json_load(val: Any, default: Any) -> Any:
        if val is None:
            return default
        if isinstance(val, (dict, list)):
            return val
        try:
            return json.loads(val or (json.dumps(default)))
        except json.JSONDecodeError:
            return default

    def upsert_recommendation(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        now = _iso(_utcnow())
        self._conn.execute(
            """
            insert into recommendations (
                id, tenant_id, building_id, equipment_id, fault_id, rec_type, title, description,
                state, severity, owner, evidence, recommended_action, expected_impact, confidence,
                risk, comfort_impact, verification_plan, expected_saving_aed, verified_saving_aed,
                approved_by, implemented_at, verified_at, work_order_id, created_at, updated_at
            ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            on conflict(id) do update set
                state=excluded.state, severity=excluded.severity, owner=excluded.owner,
                evidence=excluded.evidence, recommended_action=excluded.recommended_action,
                expected_impact=excluded.expected_impact, confidence=excluded.confidence,
                risk=excluded.risk, comfort_impact=excluded.comfort_impact,
                verification_plan=excluded.verification_plan,
                expected_saving_aed=excluded.expected_saving_aed,
                verified_saving_aed=excluded.verified_saving_aed,
                approved_by=excluded.approved_by, implemented_at=excluded.implemented_at,
                verified_at=excluded.verified_at, work_order_id=excluded.work_order_id,
                updated_at=excluded.updated_at
            """,
            (
                rec["id"], rec.get("tenant_id"), rec["building_id"], rec.get("equipment_id"),
                rec.get("fault_id"), rec.get("rec_type", "fdd_action"), rec["title"],
                rec.get("description", ""), rec.get("state", "DETECTED"), rec.get("severity", "warning"),
                rec.get("owner"), json.dumps(rec.get("evidence") or {}),
                rec.get("recommended_action") or rec.get("description"),
                json.dumps(rec.get("expected_impact") or {}), rec.get("confidence"),
                rec.get("risk"), rec.get("comfort_impact"), rec.get("verification_plan"),
                rec.get("expected_saving_aed"), rec.get("verified_saving_aed"),
                rec.get("approved_by"), rec.get("implemented_at"), rec.get("verified_at"),
                rec.get("work_order_id"), rec.get("created_at", now), now,
            ),
        )
        self._conn.commit()
        return self.get_recommendation(rec["id"]) or rec

    def get_recommendation(self, rec_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute("select * from recommendations where id=?", (rec_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["evidence"] = self._json_load(d.get("evidence"), {})
        d["expected_impact"] = self._json_load(d.get("expected_impact"), {})
        return d

    def list_recommendations(
        self, building_id: Optional[str] = None, *, limit: int = 100
    ) -> List[Dict[str, Any]]:
        if building_id:
            rows = self._conn.execute(
                "select * from recommendations where building_id=? order by created_at desc limit ?",
                (building_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "select * from recommendations order by created_at desc limit ?", (limit,)
            ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["evidence"] = self._json_load(d.get("evidence"), {})
            d["expected_impact"] = self._json_load(d.get("expected_impact"), {})
            out.append(d)
        return out

    def insert_recommendation_audit(self, **kwargs: Any) -> None:
        self._conn.execute(
            """
            insert into recommendation_audit (
                audit_id, recommendation_id, action, previous_state, new_state,
                actor_user_id, comment, created_at
            ) values (?,?,?,?,?,?,?,?)
            """,
            (
                kwargs["audit_id"], kwargs["recommendation_id"], kwargs["action"],
                kwargs.get("previous_state"), kwargs.get("new_state"),
                kwargs.get("actor_user_id"), kwargs.get("comment"), _iso(_utcnow()),
            ),
        )
        self._conn.commit()

    # ---- Savings / M&V ----

    def upsert_savings_opportunity(self, opp: Dict[str, Any]) -> Dict[str, Any]:
        now = _iso(_utcnow())
        self._conn.execute(
            """
            insert into savings_opportunities (
                id, tenant_id, building_id, recommendation_id, title, state,
                baseline_kwh, expected_kwh, actual_kwh, avoided_kwh, tariff_aed_per_kwh,
                expected_saving_aed, verified_saving_aed, confidence, methodology,
                data_coverage_pct, notes, measurement_period_start, measurement_period_end,
                implementation_date, before_energy_kwh, after_energy_kwh, normalized_baseline_kwh,
                weather_context, schedule_context, energy_saved_kwh, cost_saved, currency,
                uncertainty, verification_status, excluded_periods, calculation_version,
                created_at, updated_at
            ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            on conflict(id) do update set
                state=excluded.state, actual_kwh=excluded.actual_kwh, avoided_kwh=excluded.avoided_kwh,
                verified_saving_aed=excluded.verified_saving_aed, notes=excluded.notes,
                after_energy_kwh=excluded.after_energy_kwh, energy_saved_kwh=excluded.energy_saved_kwh,
                cost_saved=excluded.cost_saved, verification_status=excluded.verification_status,
                updated_at=excluded.updated_at
            """,
            (
                opp["id"], opp.get("tenant_id"), opp["building_id"], opp.get("recommendation_id"),
                opp["title"], opp.get("state", "POTENTIAL"),
                opp.get("baseline_kwh", 0), opp.get("expected_kwh", 0), opp.get("actual_kwh"),
                opp.get("avoided_kwh"), opp.get("tariff_aed_per_kwh", 0.38),
                opp.get("expected_saving_aed", 0), opp.get("verified_saving_aed"),
                opp.get("confidence", 0.5), opp.get("methodology", "baseline_comparison"),
                opp.get("data_coverage_pct", 0), opp.get("notes"),
                opp.get("measurement_period_start"), opp.get("measurement_period_end"),
                opp.get("implementation_date"), opp.get("before_energy_kwh"),
                opp.get("after_energy_kwh"), opp.get("normalized_baseline_kwh"),
                json.dumps(opp.get("weather_context") or {}),
                json.dumps(opp.get("schedule_context") or {}),
                opp.get("energy_saved_kwh"), opp.get("cost_saved"),
                opp.get("currency", "AED"), opp.get("uncertainty"),
                opp.get("verification_status"), json.dumps(opp.get("excluded_periods") or []),
                opp.get("calculation_version", "mv_v1"),
                opp.get("created_at", now), now,
            ),
        )
        self._conn.commit()
        return self.get_savings_opportunity(opp["id"]) or opp

    def get_savings_opportunity(self, opp_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "select * from savings_opportunities where id=?", (opp_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["weather_context"] = self._json_load(d.get("weather_context"), {})
        d["schedule_context"] = self._json_load(d.get("schedule_context"), {})
        d["excluded_periods"] = self._json_load(d.get("excluded_periods"), [])
        return d

    def list_savings_opportunities(
        self, building_id: Optional[str] = None, *, limit: int = 100
    ) -> List[Dict[str, Any]]:
        if building_id:
            rows = self._conn.execute(
                "select * from savings_opportunities where building_id=? order by created_at desc limit ?",
                (building_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "select * from savings_opportunities order by created_at desc limit ?", (limit,)
            ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["weather_context"] = self._json_load(d.get("weather_context"), {})
            d["schedule_context"] = self._json_load(d.get("schedule_context"), {})
            d["excluded_periods"] = self._json_load(d.get("excluded_periods"), [])
            out.append(d)
        return out

    def insert_savings_audit(self, **kwargs: Any) -> None:
        self._conn.execute(
            """
            insert into savings_audit (
                audit_id, savings_id, action, previous_state, new_state,
                actor_user_id, comment, created_at
            ) values (?,?,?,?,?,?,?,?)
            """,
            (
                kwargs["audit_id"], kwargs["savings_id"], kwargs["action"],
                kwargs.get("previous_state"), kwargs.get("new_state"),
                kwargs.get("actor_user_id"), kwargs.get("comment"), _iso(_utcnow()),
            ),
        )
        self._conn.commit()

    # ---- Gateway tokens ----

    def create_gateway_token(
        self,
        *,
        token_id: str,
        gateway_id: str,
        token_hash: str,
        label: str,
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = _iso(_utcnow())
        self._conn.execute(
            """
            insert into gateway_tokens (token_id, gateway_id, token_hash, label, created_at, revoked_at, expires_at)
            values (?, ?, ?, ?, ?, null, ?)
            """,
            (token_id, gateway_id, token_hash, label, now, _iso(expires_at)),
        )
        self._conn.commit()
        return {
            "token_id": token_id,
            "gateway_id": gateway_id,
            "label": label,
            "created_at": now,
            "expires_at": _iso(expires_at),
        }

    def get_gateway_token_by_hash(self, token_hash: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "select * from gateway_tokens where token_hash=?",
            (token_hash,),
        ).fetchone()
        return dict(row) if row else None

    def revoke_gateway_token(self, token_id: str) -> bool:
        now = _iso(_utcnow())
        cur = self._conn.execute(
            "update gateway_tokens set revoked_at=? where token_id=? and revoked_at is null",
            (now, token_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def list_gateway_tokens(self, gateway_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            """
            select token_id, gateway_id, label, created_at, revoked_at, expires_at
            from gateway_tokens where gateway_id=? order by created_at desc
            """,
            (gateway_id,),
        ).fetchall()
        return [dict(r) for r in rows]

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
    """Return (backend_kind, error_message).

    backend_kind: memory | sqlite | supabase | supabase_ingest_gated | unavailable
    """
    backend = (settings.telemetry_store_backend or "auto").lower()

    if settings.app_env == "test" or backend == "memory":
        return "memory", None

    if backend == "sqlite":
        return "sqlite", None

    url_ok = bool(settings.supabase_url) and not settings.supabase_url.startswith("https://your-")
    service_ok = bool(settings.supabase_service_key) and not _placeholder_key(
        settings.supabase_service_key
    )
    anon_ok = bool(settings.supabase_key) and not _placeholder_key(settings.supabase_key)
    ingest_ok = bool(settings.ingest_api_key)

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
        if (
            settings.telemetry_ingest_gated_supabase
            and url_ok
            and anon_ok
            and ingest_ok
        ):
            return (
                "supabase_ingest_gated",
                "Lovable Cloud registry via ingest-gated Supabase REST (no Supabase dashboard account required)",
            )
        return (
            "unavailable",
            "Durable telemetry registry required in production (DEMO_MODE=false). "
            "For Lovable Cloud: set TELEMETRY_INGEST_GATED_SUPABASE=true with "
            "SUPABASE_URL, SUPABASE_KEY, and INGEST_API_KEY.",
        )

    return "sqlite", None


def get_telemetry_store_status() -> Dict[str, Any]:
    """Safe telemetry registry status for health endpoints — never includes secrets."""
    from app.config import get_settings

    settings = get_settings()
    resolved, error = resolve_telemetry_backend(settings)

    if _store is not None:
        active_path = getattr(_store, "db_path", "unknown")
        auth_mode = getattr(_store, "auth_mode", None)
        if active_path == "supabase":
            active = "supabase_ingest_gated" if auth_mode == "ingest_gated" else "supabase"
        elif active_path == ":memory:":
            active = "memory"
        else:
            active = "sqlite"
    else:
        active = resolved if resolved != "unavailable" else "none"

    required = _is_production_live(settings)
    if resolved == "unavailable":
        status = "not_configured"
    elif active in ("supabase", "supabase_ingest_gated"):
        status = "connected"
    elif active == "sqlite" and required:
        status = "degraded"
    elif active in ("sqlite", "memory"):
        status = "connected"
    else:
        status = "unknown"

    durable = active in ("supabase", "supabase_ingest_gated")
    return {
        "backend": active,
        "durable": durable,
        "required": required,
        "status": status,
        "message": error,
        "auth_mode": "service_role" if active == "supabase" else (
            "ingest_gated" if active == "supabase_ingest_gated" else None
        ),
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
        elif resolved in ("supabase", "supabase_ingest_gated"):
            from app.services.supabase_telemetry_store import SupabaseTelemetryStore

            if resolved == "supabase":
                auth_key = settings.supabase_service_key
                auth_mode = "service_role"
                logger.info("Telemetry registry: Supabase PostgREST (service_role)")
            else:
                auth_key = settings.supabase_key
                auth_mode = "ingest_gated"
                logger.info(
                    "Telemetry registry: Lovable Cloud ingest-gated Supabase REST (durable Postgres)"
                )
            _store = SupabaseTelemetryStore(settings.supabase_url, auth_key, auth_mode=auth_mode)
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
