# Edge Architecture — BuildOpt (Phase 3)

## Deployment model

```text
BMS LAN (Metasys REST)
        │
        ▼
  buildopt-edge/          ← customer VM / industrial PC / Docker
        │
        │  HTTPS outbound only
        ▼
  buildopt-backend (Railway)
        │
        ├── POST /api/v1/discovery/points/batch
        ├── POST /api/v1/telemetry/batch
        ├── POST /api/v1/gateways/heartbeat
        └── GET  /api/v1/buildings/{id}/telemetry/current
```

## Package layout

`buildopt-edge/` — standalone Python service (see README in that folder).

| Module | Role |
|--------|------|
| `connectors/base.py` | Vendor-neutral `BuildingConnector` interface (read-only) |
| `connectors/metasys.py` | Metasys REST — auth, discover, read PV |
| `connectors/{bacnet,modbus,mqtt,opcua}.py` | Placeholders (BETA/PLANNED — non-production) |
| `storage/local_queue.py` | SQLite WAL store-and-forward with stable event IDs |
| `telemetry/validator.py` | Three-timestamp provenance + stable event_id |
| `telemetry/uploader.py` | Cloud batch, discovery sync, heartbeat metrics |
| `security/credentials.py` | Env-only secrets — never logged |

## Gateway states

`ONLINE` · `DEGRADED` (clock drift) · `STALE` · `OFFLINE` · `CONNECTOR_ERROR` · `CLOUD_ERROR` · `NOT_CONFIGURED`

## Queue overflow policy

When queue exceeds `max_rows` (default 50,000):

1. Log **CRITICAL** health event
2. Drop **oldest** unacknowledged events (explicit policy — not silent)
3. Never drop without logging

Events exceeding max retry attempts are **retained** in queue (no silent deletion).

## Pilot bootstrap (Phase 4)

`config/mapped_points.json` (gitignored) is **bootstrap/fallback only**. Production path:

```text
Metasys Discovery → Raw Point Registry → Semantic Approval → GET /gateways/{id}/collection-config → Edge Collection
```

Edge env: prefer `GATEWAY_API_KEY` (`bo_gw_*` scoped token) over shared `INGEST_API_KEY`.

## Auth (Phase 4)

- Scoped gateway tokens: `bo_gw_{gateway_id}_*` — telemetry, heartbeat, discovery, collection-config
- Master `INGEST_API_KEY`: token issuance/revocation only (`verify_master_ingest_key`)
- Gateway identity bound server-side; cross-tenant/building spoofing rejected
