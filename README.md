# BuildOpt AI Backend

Production-grade FastAPI backend for **BuildOpt AI** — a B2B smart building optimization platform for the GCC market (UAE/Dubai).

The frontend at [build-opt.site](https://build-opt.site) connects to this API when `DEMO_MODE=false`.

## Quick Start

```bash
# Copy environment file
cp .env.example .env

# Run with Docker (recommended)
docker compose up --build

# Or run locally
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Demo Mode

Set `DEMO_MODE=true` in `.env` to serve realistic simulated building data without BACnet, Modbus, MQTT, or JCI hardware. This matches the frontend simulation engine ranges:

- HVAC power: 180–220 kW
- Chiller COP: 3.2–4.1
- Building temp: 22–24°C
- Energy savings: 18–23%
- Active alerts: 2–5

## Architecture

BuildOpt sits **above** existing BMS systems (Johnson Controls Metasys, OpenBlue, etc.) via:

- BACnet/IP (BAC0)
- Modbus TCP (pymodbus)
- MQTT (paho-mqtt)
- JCI Metasys REST API v4

Time-series data flows to **InfluxDB**. Alerts push to **Supabase** realtime for the frontend.

## Key Endpoints

| Group | Base Path |
|-------|-----------|
| Health | `/api/v1/health` |
| Buildings | `/api/v1/buildings` |
| Energy | `/api/v1/energy` |
| Equipment | `/api/v1/equipment` |
| Alerts | `/api/v1/alerts` |
| ML | `/api/v1/ml` |
| JCI Metasys | `/api/v1/jci` |
| GCC Features | `/api/v1/gcc` |

## Deployment (Railway.app)

See **[DEPLOYMENT.md](./DEPLOYMENT.md)** for full Railway + Lovable setup.

```bash
# Railway uses Dockerfile.railway (lean deps) via railway.toml
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Set `ALLOWED_ORIGINS=https://build-opt.site,https://www.build-opt.site` for CORS.

Connect the Lovable frontend: see **[frontend-integration/LOVABLE_SETUP.md](./frontend-integration/LOVABLE_SETUP.md)**.

Production / real BMS integration: see **[PRODUCTION.md](./PRODUCTION.md)**.

## Testing

```bash
pytest tests/ -v
```

## Notes

- All timestamps are UTC; display uses `Asia/Dubai`.
- JCI Metasys JWT tokens auto-refresh every 14 minutes.
- BACnet requires the server to be on the same subnet as the BMS.
- Error responses include English and Arabic messages.
