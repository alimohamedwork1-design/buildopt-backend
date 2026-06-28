# BuildOpt — connection status

## Connected now (automated)

| Connection | Status | URL |
|------------|--------|-----|
| **Frontend → Railway** | Live | build-opt.site → buildopt-backend-production.up.railway.app |
| **Railway API** | Online | /api/v1/health |
| **Ingest API** | Live | POST /api/v1/ingest/live |
| **InfluxDB on Railway** | Service added | influxdb.railway.internal:8086 |
| **Supabase alert webhook** | Configured | Railway → edge function URL (deploy via Lovable) |

Check all connections:
```
GET https://buildopt-backend-production.up.railway.app/api/v1/health/connections
```

---

## Your action in Lovable (2 prompts)

### 1. Wire all pages to API
Paste **`frontend-integration/LOVABLE_WIRE_ALL.md`** into Lovable chat → republish.

### 2. Deploy Supabase edge function (no dashboard access)
Paste **`frontend-integration/LOVABLE_SUPABASE_EDGE.md`** into Lovable chat.

This creates `sync-bms-alert` edge function so Railway can push alerts to Supabase without you holding the service_role key.

Secret to add in **Lovable Cloud → Secrets**:
```
BUILDOPT_WEBHOOK_SECRET=buildopt-alert-sync-2026-secret
```
(Same value already set on Railway as `ALERT_WEBHOOK_SECRET`)

---

## When you get Metasys credentials (site IT)

Railway → Variables:
```env
JCI_METASYS_HOST=https://...
JCI_METASYS_USERNAME=...
JCI_METASYS_PASSWORD=...
DEMO_MODE=false
```

---

## Edge gateway (on-site BACnet/Modbus)

```powershell
cd edge
docker compose up -d
```

---

## Architecture

```
build-opt.site ──► Railway API ──► InfluxDB (Railway internal)
                      │
                      ├──► Supabase edge fn (via Lovable)
                      └──► Edge agent (on-site BMS)
```
