# Phase 3 Pre-Implementation Audit

Baseline: backend `15ce354`, frontend `693a55b`  
Date: 2026-08-29

## Scope

Audit of Phase 2 edge connectivity before implementing production telemetry, raw point registry, and data provenance.

---

## buildopt-edge

| Check | Status | Finding |
|-------|--------|---------|
| Queue survives restart | **PASS** | SQLite file on disk (`EDGE_QUEUE_DB`); schema persisted |
| SQLite durable storage | **PARTIAL** | No WAL mode; single connection; no graceful shutdown flush |
| Replay after cloud recovery | **PARTIAL** | Dequeue-before-ack; crash after HTTP 200 before ack can duplicate cloud writes |
| Telemetry deduplication | **PARTIAL** | Edge dedupe key `building:point:timestamp`; cloud dedupe only within single HTTP request |
| Duplicate batches → duplicate TS | **FAIL** | No cross-batch `event_id` idempotency; Influx writes use server `now()` not source time |
| Timestamps survive replay | **FAIL** | Cloud `InfluxService.write_point()` ignores edge timestamp |
| Failed uploads remain queued | **PASS** | Enqueue on upload failure |
| Acknowledged records removed | **PASS** | `ack()` deletes row |
| Queue size bounded | **PARTIAL** | 50k max with silent oldest-row deletion; no health event |
| Max retry policy | **FAIL** | Drops events after 10 attempts with no dead-letter |
| Metasys endpoints | **PASS** | Uses documented Metasys REST v4 login/objects/PV paths only |
| Writeback disabled | **PASS** | `read_only=True`, `writeback: False` in capabilities |
| Placeholder connectors | **PASS** | BACnet/Modbus `BETA`, MQTT/OPC-UA `PLANNED` |
| Stable event IDs | **FAIL** | No `event_id` in edge payload |
| Three timestamps | **FAIL** | Only single `timestamp`; no `edge_received_at` / provenance |
| Replay metrics | **FAIL** | Heartbeat lacks queue age, replay counters, clock drift |

---

## Cloud API (Phase 2)

| Check | Status | Finding |
|-------|--------|---------|
| `POST /telemetry/batch` | **PARTIAL** | Accepts batch; no registry validation; partial store silent |
| `POST /gateways/heartbeat` | **PARTIAL** | Auth weaker than batch endpoint in production |
| `GET /gateways` | **FAIL** | Unauthenticated; in-memory only |
| Gateway tenant binding | **FAIL** | Self-asserted `tenant_id`/`building_id`; no server validation |
| Raw point registry | **FAIL** | Not implemented |
| Current point state | **FAIL** | Not implemented |
| Influx read/write alignment | **FAIL** | Writes `telemetry_point`; reads aggregate `total_kw` etc. |
| Idempotency store | **FAIL** | Not implemented |

---

## Legacy edge/agent.py

| Check | Status | Finding |
|-------|--------|---------|
| Duplicate ingestion risk | **FAIL** | Posts to `/ingest/live` (snapshots) parallel to `/telemetry/batch` |
| Different heartbeat path | **PARTIAL** | Uses `/ingest/heartbeat` not `/gateways/heartbeat` |
| Fabricated defaults | **FAIL** | Partial BACnet failure fills hardcoded sensor defaults |
| Gateway identity | **FAIL** | No `gateway_id`; cannot distinguish from buildopt-edge |
| Decision | **DEPRECATE (A)** | Mark deprecated; require `LEGACY_EDGE_ENABLED=true` to run; document migration to buildopt-edge |

---

## P0 Fixes (must complete before Phase 3 continuation)

1. **Influx timestamp preservation** — write with source timestamp, not server now
2. **Stable event_id + cloud idempotency** — prevent duplicate time-series on replay
3. **Gateway identity validation** — bind gateway_id → tenant/building server-side
4. **Auth alignment** — heartbeat/list gateways require same ingest key policy
5. **Legacy agent deprecation** — prevent ambiguous dual ingestion
6. **Edge queue hardening** — WAL, backoff, no silent drop without CRITICAL event
7. **Three-timestamp schema** — source, edge, cloud provenance

---

## Phase 3 Implementation Plan

Proceed with: raw point registry, discovery sync, validation pipeline, current state, freshness engine, replay metrics, frontend provenance wiring, and comprehensive tests.
