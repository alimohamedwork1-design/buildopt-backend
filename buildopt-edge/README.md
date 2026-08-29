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

1. **Preferred:** Issue scoped token via cloud ops (`POST /gateways/{id}/tokens`), set `GATEWAY_API_KEY=bo_gw_...`
2. **Fallback bootstrap:** copy `config/mapped_points.json.example` → `mapped_points.json`
3. Set environment (never commit passwords):

```bash
export BUILDING_ID=your-building-id
export GATEWAY_ID=your-gateway-id
export GATEWAY_API_KEY=bo_gw_...   # scoped edge token (preferred)
# export INGEST_API_KEY=...        # ops/bootstrap only — not required on edge when GATEWAY_API_KEY set
export METASYS_HOST=https://metasys.site.local
export METASYS_USERNAME=...
export METASYS_PASSWORD=...
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
