# BuildOpt Telemetry Schema (Phase 3)

## Measurement

| Property | Value |
|----------|-------|
| **Measurement** | `telemetry_point` |
| **Primary timestamp** | `source_timestamp` when available, else `edge_received_at` |
| **Cloud receipt** | Stored in Postgres `point_current_state.last_cloud_received_at` (not Influx field) |

## Tags (low cardinality)

| Tag | Purpose |
|-----|---------|
| `tenant_id` | Tenant isolation |
| `building_id` | Building scope |
| `gateway_id` | Edge gateway identity |
| `connector_id` | Connector type (`metasys`, etc.) |
| `point_id` | Registry UUID |
| `source_point_id` | Immutable BMS object ID |
| `source` | Source system (`metasys`) |

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `value` | float | Primary reading |
| `quality` | string | Normalized quality enum |
| `source_quality` | string | Raw source quality when reported |
| `source_timestamp_missing` | bool | True when BMS did not provide timestamp |

## Three timestamps

| Timestamp | Location | Meaning |
|-----------|----------|---------|
| `source_timestamp` | Edge payload + Postgres + Influx time | BMS-reported time |
| `edge_received_at` | Edge payload + Postgres | When edge read the value |
| `cloud_received_at` | Postgres current state | When cloud accepted event |

**Replay rule:** Original `source_timestamp` and `edge_received_at` are never overwritten during queue replay.

## Idempotency

Stable `event_id` = SHA256(`gateway|building|connector|source_point|source_ts|value`)

Cloud stores processed IDs in `telemetry_events` table.

## Registry backends

| Environment | `TELEMETRY_STORE_BACKEND` | Backend | Durability |
|-------------|---------------------------|---------|------------|
| Test | (default) | SQLite `:memory:` | Ephemeral |
| Development / demo | `auto` without service key | SQLite file | Local dev only |
| Production (Lovable Cloud) | `auto` + `TELEMETRY_INGEST_GATED_SUPABASE=true` | Supabase PostgREST (ingest-gated) | **Durable** (migration 007) |
| Production (self-hosted Supabase) | `auto` + `SUPABASE_SERVICE_KEY` | Supabase PostgREST (service_role) | **Durable** |
| Production misconfigured | `auto` without ingest-gated or service key | **NOT_CONFIGURED** | Ingest returns 503 — no silent SQLite fallback |

**Lovable Cloud users** do not need a separate Supabase account or `SUPABASE_SERVICE_KEY`. Railway uses `SUPABASE_URL` + `SUPABASE_KEY` (publishable) from Lovable, with `INGEST_API_KEY` enforcing writes at the backend API layer.

Health: `GET /api/v1/health/connections` → `telemetry_store.backend`, `durable`, `status`.

## Retention assumptions

- Influx: default bucket retention (configure per deployment)
- Postgres current state: always latest value per point
- Event idempotency: retain for operational window (pilot: indefinite in SQLite/Postgres)

## Query examples

```flux
from(bucket: "building_metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "telemetry_point")
  |> filter(fn: (r) => r.building_id == "burj-khalifa-01")
  |> filter(fn: (r) => r.source_point_id == "metasys-object-id")
```

## Cardinality considerations

- Do **not** tag high-cardinality values (raw object paths, alarm text)
- `point_id` UUID is acceptable — bounded by registered points
- Prefer Postgres current-state API for latest-value UI; use Influx for history

## Infrastructure state

When Influx is not configured (`DEMO_MODE=true` or missing token), API returns:

```json
{
  "influx": {
    "configured": false,
    "status": "simulated",
    "persistence": false
  }
}
```

Current point state remains available via Postgres/SQLite registry regardless of Influx.

## Phase 4 — History API

`GET /api/v1/buildings/{building_id}/telemetry/history`

| Param | Bounds |
|-------|--------|
| `hours` | 1–168 |
| `limit` | 1–2000 |
| `every` | `1m`, `5m`, `15m`, `30m`, `1h`, `2h` |

Returns typed states: `OK`, `NO_DATA`, `INFLUX_UNAVAILABLE`. Flux tags sanitized; point_id validated against registry.

## Phase 4 — Gateway tokens (migration 008)

Table `gateway_tokens`: `token_hash` unique, FK to `gateways`. Plaintext never stored. Edge uses `GATEWAY_API_KEY` (`bo_gw_*`).
