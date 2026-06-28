# Edge Gateway

Runs **on the building LAN** to read BACnet/Modbus and push live data to Railway.

## Setup

```bash
cd edge
cp .env.example .env
# Edit .env — set INGEST_API_KEY (same as Railway INGEST_API_KEY)
docker compose up -d
```

## Variables

| Variable | Description |
|----------|-------------|
| `RAILWAY_API_URL` | `https://buildopt-backend-production.up.railway.app` |
| `INGEST_API_KEY` | Shared secret with Railway |
| `BUILDING_ID` | e.g. `burj-khalifa-01` |
| `MODBUS_HOST` | BMS Modbus IP on local subnet |

Data is POSTed to `POST /api/v1/ingest/live` every 30 seconds.
