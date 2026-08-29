# BuildOpt Data Provenance

Every live UI value must be traceable through an auditable chain.

## Provenance chain

```
Tenant
  └── Building
        └── Gateway (gateway_id)
              └── Connector (connector_id)
                    └── Raw Point (source_point_id)
                          └── Source system (metasys)
                                └── Timestamps (source / edge / cloud)
                                      └── Quality (source + normalized)
                                            └── Freshness state
```

## How BuildOpt proves origin

1. **Gateway registration** — First authenticated heartbeat binds `gateway_id` → `tenant_id` + `building_id`. Cloud rejects cross-tenant/building uploads.

2. **Raw Point Registry** — Discovery sync registers immutable `source_point_id` with connector metadata. Upserts use `UNIQUE(tenant_id, connector_id, source_point_id)`.

3. **Telemetry events** — Each reading carries stable `event_id`, three timestamps, and quality. Cloud validates against registry before storage.

4. **Idempotency** — Replayed events (timeout, edge restart, cloud reconnect) match existing `event_id` and are counted as duplicates — no second time-series point.

5. **Current state** — Latest value served from `point_current_state` with freshness computed from `last_cloud_received_at` vs `expected_interval_seconds`. Production persistence uses Supabase Postgres (migration 007); SQLite is dev/test only unless explicitly configured.

6. **Frontend display** — Live Telemetry shows source name, quality, freshness state, and connector. No mock substitution in live mode.

## Pilot bootstrap: mapped_points.json (fallback)

For Phase 3–4 pilot, edge may load `config/mapped_points.json` (gitignored) **or** fetch approved config from cloud.

```
Metasys Discovery
  → Raw Point Registry
  → Semantic Suggestions + Human Approval
  → GET /gateways/{gateway_id}/collection-config
  → Edge Collection (approved points only)
```

Manual JSON is bootstrap/fallback — not the permanent architecture.

## Gateway auth (Phase 4)

- **Production edge:** `GATEWAY_API_KEY` scoped token (`bo_gw_*`)
- **Ops/bootstrap:** master `INGEST_API_KEY` for token issuance only
- Per-gateway tokens stored as SHA-256 hashes (migration 008)
