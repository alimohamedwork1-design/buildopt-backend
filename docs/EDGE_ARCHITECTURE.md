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

## Credential security

- Edge reads `METASYS_*` from environment or Docker secrets
- Passwords never returned in API responses
- Shared `X-API-Key` for pilot; gateway identity bound server-side

## Legacy (deprecated)

`edge/agent.py` is **deprecated**. Requires `LEGACY_EDGE_ENABLED=true` to run. Use `buildopt-edge/` for production telemetry with provenance.

## Pilot bootstrap

`config/mapped_points.json` (gitignored) bootstraps collection. Edge syncs discovered points to Raw Point Registry via `/discovery/points/batch`.
