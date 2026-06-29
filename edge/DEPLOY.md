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
| `EDGE_QUEUE_DB` | `/data/edge_queue.db` |
| `INGEST_MAX_RETRIES` | `5` |

Edit [`bacnet_points.json`](bacnet_points.json) per building — maps logical keys to BACnet device/object IDs.

```bash
docker compose --profile edge-agent-bacnet up -d
```

Heartbeat: agent POSTs to `/api/v1/ingest/heartbeat` every poll cycle.

## Verify

- Backend `GET /api/v1/health/protocols` shows `bacnet` / `modbus` connected
- Frontend **Data Health** and **Live Telemetry** show live badge when `demo_mode=false`

See [`agent.py`](agent.py) and [`docker-compose.yml`](docker-compose.yml).
