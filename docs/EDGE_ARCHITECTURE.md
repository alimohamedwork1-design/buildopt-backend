# Edge Architecture — BuildOpt

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
        ├── POST /api/v1/telemetry/batch
        ├── POST /api/v1/gateways/heartbeat
        └── POST /api/v1/ingest/live (legacy snapshots)
```

## Package layout

`buildopt-edge/` — standalone Python service (see README in that folder).

| Module | Role |
|--------|------|
| `connectors/base.py` | Vendor-neutral `BuildingConnector` interface |
| `connectors/metasys.py` | Metasys REST — auth, discover, read PV |
| `connectors/{bacnet,modbus,mqtt,opcua}.py` | Placeholders (BETA/PLANNED) |
| `storage/local_queue.py` | SQLite store-and-forward |
| `telemetry/uploader.py` | Cloud batch + heartbeat |
| `security/credentials.py` | Env-only secrets — never logged |

## Gateway states

`ONLINE` · `DEGRADED` · `OFFLINE` · `CONNECTOR_ERROR` · `CLOUD_ERROR` · `NOT_CONFIGURED`

## Credential security

- Edge reads `METASYS_*` from environment or Docker secrets
- Passwords never returned in API responses (cloud `connection_store` encrypts at rest)
- Frontend submits credentials once over HTTPS → backend encrypted store

## Legacy

`edge/agent.py` remains for BACnet/Modbus snapshot ingest to `/ingest/live`.
