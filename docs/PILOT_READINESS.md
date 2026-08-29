# Pilot Readiness — Phase 3 Checkpoint

Status key: **PASS** · **PARTIAL** · **FAIL** · **BLOCKED**

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Edge starts after reboot/restart | **PARTIAL** | SQLite WAL persists queue; graceful shutdown handler added |
| 2 | Metasys connector initializes | **PASS** | Production REST v4 path; read-only |
| 3 | Raw points can register | **PASS** | `POST /discovery/points/batch` + SQLite/Postgres registry |
| 4 | Telemetry batch accepted | **PASS** | Validation pipeline with per-event reporting |
| 5 | Duplicate telemetry rejected/idempotent | **PASS** | Stable `event_id` + `telemetry_events` store |
| 6 | Historical telemetry stored when Influx configured | **PARTIAL** | Writes preserve source timestamp; requires `DEMO_MODE=false` + token |
| 7 | Current point state available | **PASS** | Postgres/SQLite `point_current_state` |
| 8 | Source timestamp preserved | **PASS** | Never overwritten on replay |
| 9 | Edge timestamp preserved | **PASS** | `edge_received_at` in payload + current state |
| 10 | Cloud timestamp recorded | **PASS** | `cloud_received_at` on accept |
| 11 | Freshness calculated | **PASS** | Configurable interval multipliers |
| 12 | Stale data detected | **PASS** | LIVE / STALE / OFFLINE states |
| 13 | Queue survives restart | **PASS** | SQLite on disk with WAL |
| 14 | Internet failure queues data | **PASS** | Enqueue on upload failure |
| 15 | Internet recovery replays data | **PASS** | Batch drain with replay metrics |
| 16 | Replay preserves timestamps | **PASS** | Payload immutable in queue |
| 17 | Gateway heartbeat works | **PASS** | Extended metrics + clock drift |
| 18 | Queue metrics visible | **PASS** | Heartbeat + System Status UI |
| 19 | Clock drift visible | **PASS** | `clock_drift_seconds` on heartbeat response |
| 20 | Tenant isolation tested | **PASS** | Cross-tenant/building rejection tests |
| 21 | Frontend shows real point provenance | **PARTIAL** | LiveTelemetry wired; requires live API + edge data |
| 22 | Frontend never substitutes demo telemetry | **PASS** | Live mode shows — / NO DATA / NOT CONFIGURED |

## Blockers for production pilot

1. **Real Metasys credentials** at customer site — BLOCKED on customer
2. **`INGEST_API_KEY`** configured on Railway — **PASS** (production `ingest_api=True`, batch endpoint requires key)
3. **Supabase migration 007** applied for Postgres persistence — **PASS** (applied 2026-08-29; all Phase 3 tables verified)
4. **InfluxDB** configured with `DEMO_MODE=false` — **PASS** (production `demo_mode=false`, Influx connected)
5. **Supabase-backed telemetry registry** on Railway — **PASS** (Lovable Cloud ingest-gated mode; `durable=true`, migration 007 applied)
6. **Customer `mapped_points.json`** on edge host — BLOCKED on customer

## Recommended Phase 4

Semantic Mapping V2 (approved collection config from registry), Influx history queries in UI, data-health per-point drilldown, per-gateway scoped tokens.

## Phase 4 — implemented (2026-08-29)

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | Semantic Mapping V2 from registry | **PASS** | `GET/POST /semantic/buildings/{id}/suggestions|approve|collection-config` |
| 2 | Influx `telemetry_point` history in UI | **PASS** | `GET /buildings/{id}/telemetry/history` + LiveTelemetry chart |
| 3 | Registry-backed data health drilldown | **PASS** | `GET /data-health/points/{id}` + DataHealth panel |
| 4 | Per-gateway scoped ingest tokens | **PASS** | `POST/GET/DELETE /gateways/{id}/tokens` + migration 008 |

**Migration 008** (`gateway_tokens`) applied to Lovable Cloud DB.

**Edge collection config:** `GET /api/v1/semantic/buildings/{id}/collection-config` replaces manual `mapped_points.json` once mappings are approved in registry.

**Gateway tokens:** Issue via `POST /gateways/{gateway_id}/tokens` with master `INGEST_API_KEY`; edge uses scoped `bo_gw_*` token instead of shared key.

## Phase 5 — implemented (2026-08-29)

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | Semantic review queue UI | **PASS** | Tag Mapper wired to live APIs |
| 2 | Explicit approve/reject/edit/revert | **PASS** | Audit trail on every action |
| 3 | Collection config versioning | **PASS** | Migration 009; DRAFT/ACTIVE/SUPERSEDED |
| 4 | Edge version-aware config refresh | **PASS** | Fail-safe — keeps last active config |
| 5 | Point history drilldown | **PASS** | PointDetailsPanel; Influx ≤7d |
| 6 | Equipment FDD input readiness | **PASS** | Coverage from approved mappings only |
| 7 | Zero-mock-live semantic UI | **PASS** | Honest empty/unavailable states |

**Migration 009** (`semantic_audit_log`, `collection_config_versions`) applied to Lovable Cloud DB.

**Pilot workflow:** Discovery → Review Queue → Approve → Publish Config → Edge Refresh → Point History.

## Recommended Phase 6

On-site Metasys pilot with engineer mapping session, 7-day history validation, FDD template tuning (read-only).
