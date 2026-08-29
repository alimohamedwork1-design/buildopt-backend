"""Supabase PostgREST-backed telemetry registry for durable production storage."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.services.freshness_engine import apply_quality_state, compute_freshness

logger = logging.getLogger("buildopt.telemetry.supabase")


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


def _as_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _iso(value)
    return str(value)


class SupabaseTelemetryStore:
    """Mirrors TelemetryStore via Supabase REST (migration 007 schema)."""

    db_path = "supabase"

    def __init__(self, supabase_url: str, auth_key: str, *, auth_mode: str = "service_role") -> None:
        self._base = supabase_url.rstrip("/") + "/rest/v1"
        self._key = auth_key
        self.auth_mode = auth_mode
        self._client = httpx.Client(timeout=20.0)

    def close(self) -> None:
        self._client.close()

    def _headers(self, *, prefer: Optional[str] = None, count: bool = False) -> Dict[str, str]:
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }
        prefer_parts: List[str] = []
        if prefer:
            prefer_parts.append(prefer)
        if count:
            prefer_parts.append("count=exact")
        if prefer_parts:
            headers["Prefer"] = ",".join(prefer_parts)
        return headers

    def _request(
        self,
        method: str,
        table: str,
        *,
        params: Optional[Dict[str, str]] = None,
        json_body: Any = None,
        prefer: Optional[str] = None,
        count: bool = False,
    ) -> httpx.Response:
        url = f"{self._base}/{table}"
        response = self._client.request(
            method,
            url,
            headers=self._headers(prefer=prefer, count=count),
            params=params or {},
            json=json_body,
        )
        if response.status_code >= 400:
            logger.warning(
                "Supabase %s %s failed: %s %s",
                method,
                table,
                response.status_code,
                response.text[:300],
            )
            response.raise_for_status()
        return response

    @staticmethod
    def _content_range_total(content_range: str) -> int:
        match = re.search(r"/(\d+|\*)$", content_range or "")
        if not match or match.group(1) == "*":
            return 0
        return int(match.group(1))

    @staticmethod
    def _normalize_gateway(row: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(row)
        out["enabled"] = 1 if out.get("enabled") else 0
        return out

    @staticmethod
    def _normalize_point(row: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(row)
        out["id"] = str(out["id"])
        meta = out.get("metadata")
        if isinstance(meta, str):
            out["metadata"] = json.loads(meta or "{}")
        elif meta is None:
            out["metadata"] = {}
        out["enabled"] = 1 if out.get("enabled") else 0
        for key in ("discovered_at", "last_seen_at", "created_at", "updated_at"):
            out[key] = _as_iso(out.get(key))
        return out

    @staticmethod
    def _normalize_state(row: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(row)
        out["point_id"] = str(out["point_id"])
        for key in (
            "last_source_timestamp",
            "last_edge_received_at",
            "last_cloud_received_at",
            "updated_at",
        ):
            out[key] = _as_iso(out.get(key))
        return out

    @staticmethod
    def _normalize_token_row(row: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(row)
        for key in ("created_at", "revoked_at", "expires_at"):
            out[key] = _as_iso(out.get(key))
        return out

    # ---- Gateways ----

    def register_gateway(
        self,
        *,
        gateway_id: str,
        tenant_id: str,
        building_id: str,
        connector_id: str,
    ) -> Dict[str, Any]:
        existing = self.get_gateway(gateway_id)
        if existing:
            if existing["tenant_id"] != tenant_id or existing["building_id"] != building_id:
                raise PermissionError("gateway_identity_mismatch")
            return existing
        now = _iso(_utcnow())
        row = {
            "gateway_id": gateway_id,
            "tenant_id": tenant_id,
            "building_id": building_id,
            "connector_id": connector_id,
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        }
        response = self._request(
            "POST",
            "gateways",
            json_body=row,
            prefer="return=representation",
        )
        rows = response.json()
        return self._normalize_gateway(rows[0]) if rows else self.get_gateway(gateway_id) or {}

    def get_gateway(self, gateway_id: str) -> Optional[Dict[str, Any]]:
        response = self._request(
            "GET",
            "gateways",
            params={"gateway_id": f"eq.{gateway_id}", "select": "*", "limit": "1"},
        )
        rows = response.json()
        return self._normalize_gateway(rows[0]) if rows else None

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
        existing = self._request(
            "GET",
            "raw_points",
            params={
                "tenant_id": f"eq.{tenant_id}",
                "connector_id": f"eq.{connector_id}",
                "source_point_id": f"eq.{source_point_id}",
                "select": "id",
                "limit": "1",
            },
        ).json()

        metadata = payload.get("metadata") or {}
        if existing:
            point_id = str(existing[0]["id"])
            self._request(
                "PATCH",
                "raw_points",
                params={"id": f"eq.{point_id}"},
                json_body={
                    "source_name": payload.get("source_name"),
                    "source_path": payload.get("source_path"),
                    "source_type": payload.get("source_type"),
                    "raw_unit": payload.get("raw_unit"),
                    "metadata": metadata,
                    "last_seen_at": now,
                    "updated_at": now,
                    "source": payload.get("source", "metasys"),
                    "gateway_id": payload["gateway_id"],
                    "building_id": payload["building_id"],
                },
            )
        else:
            point_id = str(uuid.uuid4())
            self._request(
                "POST",
                "raw_points",
                json_body={
                    "id": point_id,
                    "tenant_id": tenant_id,
                    "building_id": payload["building_id"],
                    "gateway_id": payload["gateway_id"],
                    "connector_id": connector_id,
                    "source": payload.get("source", "metasys"),
                    "source_point_id": source_point_id,
                    "source_name": payload.get("source_name"),
                    "source_path": payload.get("source_path"),
                    "source_type": payload.get("source_type"),
                    "raw_unit": payload.get("raw_unit"),
                    "metadata": metadata,
                    "discovered_at": now,
                    "last_seen_at": now,
                    "created_at": now,
                    "updated_at": now,
                    "enabled": True,
                    "expected_interval_seconds": int(payload.get("expected_interval_seconds") or 30),
                },
                prefer="return=minimal",
            )
            interval = int(payload.get("expected_interval_seconds") or 30)
            self._request(
                "POST",
                "point_current_state",
                params={"on_conflict": "point_id"},
                json_body={
                    "point_id": point_id,
                    "normalized_quality": "NO_DATA",
                    "freshness_state": "NO_DATA",
                    "state": "NO_DATA",
                    "expected_interval_seconds": interval,
                    "updated_at": now,
                },
                prefer="resolution=merge-duplicates,return=minimal",
            )
        return self.get_point(point_id) or {}

    def get_point(self, point_id: str) -> Optional[Dict[str, Any]]:
        response = self._request(
            "GET",
            "raw_points",
            params={"id": f"eq.{point_id}", "select": "*", "limit": "1"},
        )
        rows = response.json()
        if not rows:
            return None
        out = self._normalize_point(rows[0])
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
        rows = self._request(
            "GET",
            "raw_points",
            params={
                "tenant_id": f"eq.{tenant_id}",
                "connector_id": f"eq.{connector_id}",
                "source_point_id": f"eq.{source_point_id}",
                "select": "id",
                "limit": "1",
            },
        ).json()
        if not rows:
            return None
        return self.get_point(str(rows[0]["id"]))

    def list_points(
        self,
        *,
        tenant_id: Optional[str] = None,
        building_id: Optional[str] = None,
        gateway_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        params: Dict[str, str] = {
            "select": "id",
            "order": "last_seen_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }
        if tenant_id:
            params["tenant_id"] = f"eq.{tenant_id}"
        if building_id:
            params["building_id"] = f"eq.{building_id}"
        if gateway_id:
            params["gateway_id"] = f"eq.{gateway_id}"

        response = self._client.get(
            f"{self._base}/raw_points",
            headers=self._headers(count=True),
            params=params,
        )
        response.raise_for_status()
        total = self._content_range_total(response.headers.get("Content-Range", ""))
        rows = response.json()
        points = [p for r in rows if (p := self.get_point(str(r["id"])))]
        return points, total or len(points)

    # ---- Current state ----

    def get_current_state(self, point_id: str) -> Optional[Dict[str, Any]]:
        response = self._request(
            "GET",
            "point_current_state",
            params={"point_id": f"eq.{point_id}", "select": "*", "limit": "1"},
        )
        rows = response.json()
        return self._normalize_state(rows[0]) if rows else None

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
        row = {
            "point_id": point_id,
            "last_value": numeric,
            "last_value_text": text,
            "last_source_timestamp": _iso(source_timestamp),
            "last_edge_received_at": _iso(edge_received_at),
            "last_cloud_received_at": _iso(cloud_received_at),
            "source_quality": source_quality,
            "normalized_quality": normalized_quality,
            "freshness_seconds": freshness["freshness_seconds"],
            "expected_interval_seconds": expected_interval_seconds,
            "freshness_state": freshness["freshness_state"],
            "state": state,
            "updated_at": now,
        }
        self._request(
            "POST",
            "point_current_state",
            params={"on_conflict": "point_id"},
            json_body=row,
            prefer="resolution=merge-duplicates,return=minimal",
        )
        return self.get_current_state(point_id) or {}

    def list_building_current(
        self,
        building_id: str,
        *,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, str] = {
            "building_id": f"eq.{building_id}",
            "select": "id",
            "order": "source_name.asc",
        }
        if tenant_id:
            params["tenant_id"] = f"eq.{tenant_id}"
        rows = self._request("GET", "raw_points", params=params).json()
        out: List[Dict[str, Any]] = []
        for row in rows:
            point = self.get_point(str(row["id"]))
            if point:
                out.append(point)
        return out

    def update_point_metadata(self, point_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        now = _iso(_utcnow())
        self._request(
            "PATCH",
            "raw_points",
            params={"id": f"eq.{point_id}"},
            json_body={"metadata": metadata or {}, "updated_at": now},
            prefer="return=minimal",
        )
        return self.get_point(point_id) or {}

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
        row = {
            "token_id": token_id,
            "gateway_id": gateway_id,
            "token_hash": token_hash,
            "label": label,
            "created_at": now,
            "expires_at": _iso(expires_at),
        }
        self._request("POST", "gateway_tokens", json_body=row, prefer="return=minimal")
        return {**row, "created_at": now}

    def get_gateway_token_by_hash(self, token_hash: str) -> Optional[Dict[str, Any]]:
        rows = self._request(
            "GET",
            "gateway_tokens",
            params={"token_hash": f"eq.{token_hash}", "limit": "1"},
        ).json()
        return self._normalize_token_row(rows[0]) if rows else None

    def revoke_gateway_token(self, token_id: str) -> bool:
        now = _iso(_utcnow())
        response = self._request(
            "PATCH",
            "gateway_tokens",
            params={"token_id": f"eq.{token_id}", "revoked_at": "is.null"},
            json_body={"revoked_at": now},
            prefer="return=minimal",
        )
        return response.status_code < 400

    def list_gateway_tokens(self, gateway_id: str) -> List[Dict[str, Any]]:
        rows = self._request(
            "GET",
            "gateway_tokens",
            params={
                "gateway_id": f"eq.{gateway_id}",
                "select": "token_id,gateway_id,label,created_at,revoked_at,expires_at",
                "order": "created_at.desc",
            },
        ).json()
        return [self._normalize_token_row(r) for r in rows]

    def insert_semantic_audit(self, **kwargs: Any) -> Dict[str, Any]:
        now = _iso(_utcnow())
        row = {
            "audit_id": kwargs["audit_id"],
            "point_id": kwargs.get("point_id"),
            "building_id": kwargs["building_id"],
            "tenant_id": kwargs.get("tenant_id"),
            "gateway_id": kwargs.get("gateway_id"),
            "source_point_id": kwargs.get("source_point_id"),
            "action": kwargs["action"],
            "previous_state": kwargs.get("previous_state") or {},
            "new_state": kwargs.get("new_state") or {},
            "actor_user_id": kwargs.get("actor_user_id"),
            "actor_email": kwargs.get("actor_email"),
            "comment": kwargs.get("comment"),
            "confidence": kwargs.get("confidence"),
            "created_at": now,
        }
        self._request("POST", "semantic_audit_log", json_body=row, prefer="return=minimal")
        return {"audit_id": kwargs["audit_id"], "action": kwargs["action"], "created_at": now}

    def list_semantic_audit(
        self, *, building_id: Optional[str] = None, point_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        params: Dict[str, str] = {"order": "created_at.desc", "limit": str(limit)}
        if point_id:
            params["point_id"] = f"eq.{point_id}"
        elif building_id:
            params["building_id"] = f"eq.{building_id}"
        else:
            return []
        return self._request("GET", "semantic_audit_log", params=params).json()

    def next_mapping_revision(self, building_id: str, gateway_id: Optional[str]) -> int:
        params: Dict[str, str] = {
            "building_id": f"eq.{building_id}",
            "select": "mapping_revision",
            "order": "mapping_revision.desc",
            "limit": "1",
        }
        if gateway_id:
            params["gateway_id"] = f"eq.{gateway_id}"
        rows = self._request("GET", "collection_config_versions", params=params).json()
        if not rows:
            return 1
        return int(rows[0].get("mapping_revision", 0)) + 1

    def supersede_active_config_versions(self, building_id: str, gateway_id: Optional[str]) -> None:
        params: Dict[str, str] = {"building_id": f"eq.{building_id}", "status": "eq.ACTIVE"}
        if gateway_id:
            params["gateway_id"] = f"eq.{gateway_id}"
        self._request(
            "PATCH",
            "collection_config_versions",
            params=params,
            json_body={"status": "SUPERSEDED"},
            prefer="return=minimal",
        )

    def publish_active_config_version(self, **kwargs: Any) -> Dict[str, Any]:
        """Best-effort atomic publish: DRAFT insert → supersede → activate with restore on failure."""
        building_id = kwargs["building_id"]
        gateway_id = kwargs.get("gateway_id")
        config_version = kwargs["config_version"]
        prev = self.get_active_config_version(building_id, gateway_id)
        prev_version = prev.get("config_version") if prev else None

        draft_row = dict(kwargs)
        draft_row["status"] = "DRAFT"
        draft_row["activated_at"] = None
        self.insert_config_version(**draft_row)

        try:
            self.supersede_active_config_versions(building_id, gateway_id)
            now = _iso(_utcnow())
            self._request(
                "PATCH",
                "collection_config_versions",
                params={"config_version": f"eq.{config_version}"},
                json_body={"status": "ACTIVE", "activated_at": now},
                prefer="return=minimal",
            )
        except Exception:
            if prev_version:
                try:
                    self._request(
                        "PATCH",
                        "collection_config_versions",
                        params={"config_version": f"eq.{prev_version}"},
                        json_body={"status": "ACTIVE"},
                        prefer="return=minimal",
                    )
                except Exception:
                    pass
            raise

        return {"config_version": config_version, "created_at": _iso(_utcnow()), "status": "ACTIVE"}

    def insert_config_version(self, **kwargs: Any) -> Dict[str, Any]:
        now = _iso(_utcnow())
        row = {
            "config_version": kwargs["config_version"],
            "building_id": kwargs["building_id"],
            "gateway_id": kwargs.get("gateway_id"),
            "tenant_id": kwargs.get("tenant_id"),
            "mapping_revision": kwargs["mapping_revision"],
            "point_count": kwargs["point_count"],
            "approved_count": kwargs["approved_count"],
            "status": kwargs["status"],
            "config_payload": kwargs.get("config_payload") or {},
            "created_at": now,
            "activated_at": _iso(kwargs.get("activated_at")),
        }
        self._request("POST", "collection_config_versions", json_body=row, prefer="return=minimal")
        return {"config_version": kwargs["config_version"], "created_at": now, "status": kwargs["status"]}

    def get_active_config_version(
        self, building_id: str, gateway_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        params: Dict[str, str] = {
            "building_id": f"eq.{building_id}",
            "status": "eq.ACTIVE",
            "order": "created_at.desc",
            "limit": "1",
        }
        if gateway_id:
            params["gateway_id"] = f"eq.{gateway_id}"
        rows = self._request("GET", "collection_config_versions", params=params).json()
        if not rows:
            return None
        row = dict(rows[0])
        payload = row.get("config_payload")
        if isinstance(payload, str):
            row["config_payload"] = json.loads(payload or "{}")
        return row

    def list_config_versions(self, building_id: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self._request(
            "GET",
            "collection_config_versions",
            params={
                "building_id": f"eq.{building_id}",
                "select": "config_version,building_id,gateway_id,mapping_revision,point_count,approved_count,status,created_at,activated_at",
                "order": "created_at.desc",
                "limit": str(limit),
            },
        ).json()
        return rows

    # ---- Idempotency ----

    def is_event_processed(self, event_id: str) -> bool:
        rows = self._request(
            "GET",
            "telemetry_events",
            params={"event_id": f"eq.{event_id}", "select": "event_id", "limit": "1"},
        ).json()
        return bool(rows)

    def mark_event_processed(
        self,
        *,
        event_id: str,
        tenant_id: str,
        building_id: str,
        gateway_id: str,
    ) -> None:
        self._request(
            "POST",
            "telemetry_events",
            json_body={
                "event_id": event_id,
                "tenant_id": tenant_id,
                "building_id": building_id,
                "gateway_id": gateway_id,
                "processed_at": _iso(_utcnow()),
            },
            prefer="resolution=ignore-duplicates,return=minimal",
        )

    # ---- Recommendations & savings (migration 006/011) ----

    @staticmethod
    def _normalize_rec(row: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(row)
        for key in ("evidence", "expected_impact"):
            val = out.get(key)
            if isinstance(val, str):
                out[key] = json.loads(val or "{}")
        return out

    def upsert_recommendation(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        now = _iso(_utcnow())
        row = {
            "id": rec["id"],
            "tenant_id": rec.get("tenant_id"),
            "building_id": rec["building_id"],
            "equipment_id": rec.get("equipment_id"),
            "fault_id": rec.get("fault_id"),
            "rec_type": rec.get("rec_type", "fdd_action"),
            "title": rec["title"],
            "description": rec.get("description", ""),
            "state": rec.get("state", "DETECTED"),
            "severity": rec.get("severity", "warning"),
            "owner": rec.get("owner"),
            "evidence": rec.get("evidence") or {},
            "recommended_action": rec.get("recommended_action") or rec.get("description"),
            "expected_impact": rec.get("expected_impact") or {},
            "confidence": rec.get("confidence"),
            "risk": rec.get("risk"),
            "comfort_impact": rec.get("comfort_impact"),
            "verification_plan": rec.get("verification_plan"),
            "expected_saving_aed": rec.get("expected_saving_aed"),
            "verified_saving_aed": rec.get("verified_saving_aed"),
            "approved_by": rec.get("approved_by"),
            "implemented_at": rec.get("implemented_at"),
            "verified_at": rec.get("verified_at"),
            "work_order_id": rec.get("work_order_id"),
            "created_at": rec.get("created_at", now),
            "updated_at": now,
        }
        self._request("POST", "recommendations", json_body=row, prefer="resolution=merge-duplicates,return=representation")
        rows = self._request("GET", "recommendations", params={"id": f"eq.{rec['id']}", "limit": "1"}).json()
        return self._normalize_rec(rows[0]) if rows else row

    def get_recommendation(self, rec_id: str) -> Optional[Dict[str, Any]]:
        rows = self._request("GET", "recommendations", params={"id": f"eq.{rec_id}", "limit": "1"}).json()
        return self._normalize_rec(rows[0]) if rows else None

    def list_recommendations(self, building_id: Optional[str] = None, *, limit: int = 100) -> List[Dict[str, Any]]:
        params: Dict[str, str] = {"order": "created_at.desc", "limit": str(limit)}
        if building_id:
            params["building_id"] = f"eq.{building_id}"
        rows = self._request("GET", "recommendations", params=params).json()
        return [self._normalize_rec(r) for r in rows]

    def insert_recommendation_audit(self, **kwargs: Any) -> None:
        self._request(
            "POST",
            "recommendation_audit",
            json_body={
                "audit_id": kwargs["audit_id"],
                "recommendation_id": kwargs["recommendation_id"],
                "action": kwargs["action"],
                "previous_state": kwargs.get("previous_state"),
                "new_state": kwargs.get("new_state"),
                "actor_user_id": kwargs.get("actor_user_id"),
                "comment": kwargs.get("comment"),
                "created_at": _iso(_utcnow()),
            },
            prefer="return=minimal",
        )

    @staticmethod
    def _normalize_savings(row: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(row)
        for key in ("weather_context", "schedule_context", "excluded_periods"):
            val = out.get(key)
            if isinstance(val, str):
                out[key] = json.loads(val or ("[]" if key == "excluded_periods" else "{}"))
        return out

    def upsert_savings_opportunity(self, opp: Dict[str, Any]) -> Dict[str, Any]:
        now = _iso(_utcnow())
        row = {**opp, "updated_at": now, "created_at": opp.get("created_at", now)}
        self._request("POST", "savings_opportunities", json_body=row, prefer="resolution=merge-duplicates,return=representation")
        rows = self._request("GET", "savings_opportunities", params={"id": f"eq.{opp['id']}", "limit": "1"}).json()
        return self._normalize_savings(rows[0]) if rows else row

    def get_savings_opportunity(self, opp_id: str) -> Optional[Dict[str, Any]]:
        rows = self._request("GET", "savings_opportunities", params={"id": f"eq.{opp_id}", "limit": "1"}).json()
        return self._normalize_savings(rows[0]) if rows else None

    def list_savings_opportunities(self, building_id: Optional[str] = None, *, limit: int = 100) -> List[Dict[str, Any]]:
        params: Dict[str, str] = {"order": "created_at.desc", "limit": str(limit)}
        if building_id:
            params["building_id"] = f"eq.{building_id}"
        rows = self._request("GET", "savings_opportunities", params=params).json()
        return [self._normalize_savings(r) for r in rows]

    def insert_savings_audit(self, **kwargs: Any) -> None:
        self._request(
            "POST",
            "savings_audit",
            json_body={
                "audit_id": kwargs["audit_id"],
                "savings_id": kwargs["savings_id"],
                "action": kwargs["action"],
                "previous_state": kwargs.get("previous_state"),
                "new_state": kwargs.get("new_state"),
                "actor_user_id": kwargs.get("actor_user_id"),
                "comment": kwargs.get("comment"),
                "created_at": _iso(_utcnow()),
            },
            prefer="return=minimal",
        )
