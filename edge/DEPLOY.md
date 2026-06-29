# Edge agent deployment (BACnet / Modbus)

Deploy on the building network to ingest live points when Metasys REST is unavailable.

## Prerequisites

- Docker (or Python 3.11+)
- Network access to BACnet/IP (`UDP 47808`) or Modbus TCP (`502`)
- Railway backend `INGEST_API_KEY` (set in production)

## Quick start (Docker)

```bash
cd edge
cp .env.example .env   # if present, or set vars below
```

Environment:

| Variable | Example |
|----------|---------|
| `RAILWAY_API_URL` | `https://buildopt-backend-production.up.railway.app` |
| `INGEST_API_KEY` | *(from Railway backend secrets)* |
| `BUILDING_ID` | `burj-khalifa-01` |
| `ENABLE_BACNET` | `true` |
| `BACNET_IP` | `192.168.1.100` |

```bash
docker compose up -d
```

## Verify

- Backend `GET /api/v1/health/protocols` shows `bacnet` / `modbus` connected
- Frontend **Data Health** and **Live Telemetry** show live badge when `demo_mode=false`

See [`agent.py`](agent.py) and [`docker-compose.yml`](docker-compose.yml).
