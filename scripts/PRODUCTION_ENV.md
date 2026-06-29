# Production environment — Railway `buildopt-backend`

Set these on the **buildopt-backend** service (Railway dashboard → Variables):

| Variable | Recommended value | Notes |
|----------|-------------------|--------|
| `DEMO_MODE` | `false` | Use live Influx/Metasys when connected; keep `true` until BMS is ready |
| `SUPABASE_ALERT_WEBHOOK_URL` | `https://arddnpiluxrkndzzdpfi.supabase.co/functions/v1/sync-bms-alert` | After edge function deploy |
| `ALERT_WEBHOOK_SECRET` | `buildopt-alert-sync-2026-secret` | Must match Supabase secret `BUILDOPT_WEBHOOK_SECRET` |
| `INGEST_API_KEY` | *(strong random)* | Required in production for ingest endpoints |
| `ALLOWED_ORIGINS` | `https://build-opt.site,https://buildopt-frontend-production.up.railway.app` | CORS |

Frontend **buildopt-frontend** service:

| Variable | Value |
|----------|--------|
| `VITE_API_URL` | `https://buildopt-backend-production.up.railway.app` |
| `VITE_DEMO_MODE` | `false` |
| `VITE_SUPABASE_URL` | `https://arddnpiluxrkndzzdpfi.supabase.co` |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | *(anon key)* |

## Verify

```powershell
.\scripts\verify-production.ps1
```

## Metasys

Connect via https://build-opt.site/settings?tab=bms — credentials persist on backend via `/jci/save-credentials`.
