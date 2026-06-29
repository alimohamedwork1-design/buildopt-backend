# BuildOpt Production Environment

Canonical checklist for Railway `buildopt-backend` and `buildopt-frontend`.

## Pre-cutover (`DEMO_MODE=true`)

Use while Metasys credentials and object maps are being validated.

| Variable | Value | Notes |
|----------|-------|--------|
| `DEMO_MODE` | `true` | Simulated live data; safe default |
| `APP_ENV` | `production` | Enables fail-closed ingest |
| `SECRET_KEY` | *(openssl rand -hex 32)* | Fernet encryption for Metasys passwords |
| `ALLOWED_ORIGINS` | `https://build-opt.site,https://www.build-opt.site` | CORS |
| `POLL_INTERVAL_SECONDS` | `30` | Scheduler interval |
| `INGEST_API_KEY` | *(strong random)* | Edge gateway auth |
| `SUPABASE_URL` | `https://arddnpiluxrkndzzdpfi.supabase.co` | |
| `SUPABASE_KEY` | *(anon key)* | |
| `SUPABASE_SERVICE_KEY` | *(service role)* | `bms_connections` writes |
| `ALERT_WEBHOOK_SECRET` | *(match Supabase RPC)* | Set via `supabase/SYNC_BMS_ALERT.sql` |
| `INFLUX_URL` | Influx Cloud URL | Optional until cutover |
| `INFLUX_TOKEN` | Influx token | |
| `INFLUX_ORG` | `buildopt` | |
| `INFLUX_BUCKET` | `building_metrics` | |

Frontend (`buildopt-frontend`):

| Variable | Value |
|----------|--------|
| `VITE_API_URL` | `https://buildopt-backend-production.up.railway.app` |
| `VITE_DEMO_MODE` | `false` |
| `VITE_SUPABASE_URL` | `https://arddnpiluxrkndzzdpfi.supabase.co` |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | *(anon key)* |

## Cutover (`DEMO_MODE=false`)

1. Enter Metasys credentials at https://build-opt.site/settings?tab=bms
2. Map object IDs via `PUT /api/v1/jci/buildings/{id}/objects` or edit `app/data/metasys_objects.json`
3. Set `DEMO_MODE=false` on Railway backend
4. Run `.\scripts\verify-production.ps1`
5. POST `/api/v1/health/alert-webhook/test` (requires `ALERT_WEBHOOK_SECRET`)

Additional cutover vars:

| Variable | Required |
|----------|----------|
| `INFLUX_*` | Yes for time-series |
| `INGEST_API_KEY` | Yes for edge ingest |
| `SECRET_KEY` | Must not be default |

BACnet/Modbus run on-site via `edge/` — not on Railway.

## Verify

```powershell
.\scripts\verify-production.ps1
python scripts\verify_supabase_tables.py
```
