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
2. **`INGEST_API_KEY`** configured on Railway — BLOCKED on deployment
3. **Supabase migration 007** applied for Postgres persistence — PARTIAL (SQLite fallback works for pilot dev)
4. **InfluxDB** configured with `DEMO_MODE=false` — BLOCKED on deployment config
5. **Customer `mapped_points.json`** on edge host — BLOCKED on customer

## Recommended Phase 4

Semantic Mapping V2 (approved collection config from registry), Influx history queries in UI, data-health per-point drilldown, per-gateway scoped tokens.
