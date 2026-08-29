# BuildOpt Edge Gateway

Site-local gateway for **Johnson Controls Metasys** (pilot) with store-and-forward telemetry to BuildOpt Cloud.

## Architecture

```text
BMS LAN (Metasys)
       │
       ▼
BuildOpt Edge  ──HTTPS outbound──▶  BuildOpt Cloud API
       │
       └── SQLite queue (offline buffer)
```

## Quick start

1. Copy mapped points: `config/mapped_points.json` — logical key → Metasys object ID
2. Set environment (never commit passwords):

```bash
export BUILDING_ID=your-building-id
export METASYS_HOST=https://metasys.site.local
export METASYS_USERNAME=...
export METASYS_PASSWORD=...
export INGEST_API_KEY=...
export CLOUD_API_URL=https://buildopt-backend-production.up.railway.app
```

3. Run:

```bash
docker compose up --build
```

## Connectors

| Protocol | Status |
|----------|--------|
| Metasys REST | Production pilot |
| BACnet | BETA placeholder |
| Modbus | BETA placeholder |
| MQTT | PLANNED |
| OPC-UA | PLANNED |

## Cloud endpoints

- `POST /api/v1/telemetry/batch` — batch point readings
- `POST /api/v1/gateways/heartbeat` — gateway health

Legacy edge agent remains at `../edge/agent.py` for BACnet/Modbus-only sites.
