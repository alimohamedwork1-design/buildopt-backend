# BuildOpt — Your manual steps (after code deploy)

Code is implemented. Complete these **3 admin tasks** to finish production:

---

## 1. Deploy updated backend to Railway

Push this repo to GitHub → Railway auto-redeploys, or:

```powershell
cd "C:\Users\Ali Mohamed\Projects\buildopt-backend"
git add .
git commit -m "Add production pipeline, ingest API, edge gateway"
git push
```

---

## 2. Railway variables

Copy from `railway.env.template` into **Railway → Variables**:

**Required now:**
```env
INGEST_API_KEY=<generate-random-32-char-string>
POLL_INTERVAL_SECONDS=30
SUPABASE_URL=https://arddnpiluxrkndzzdpfi.supabase.co
SUPABASE_SERVICE_KEY=<from Supabase dashboard → Settings → API → service_role>
```

**When you have InfluxDB Cloud:**
```env
INFLUX_URL=https://us-east-1-1.aws.cloud2.influxdata.com
INFLUX_TOKEN=<token>
INFLUX_ORG=buildopt
INFLUX_BUCKET=building_metrics
```

**When you have Metasys:**
```env
JCI_METASYS_HOST=https://...
JCI_METASYS_USERNAME=...
JCI_METASYS_PASSWORD=...
```

**Cutover to production data:**
```env
DEMO_MODE=false
```

---

## 3. Supabase SQL

Open **Supabase → SQL Editor** → run:

`supabase/migrations/001_building_alerts.sql`

---

## Verify

```bash
curl https://buildopt-backend-production.up.railway.app/api/v1/health
curl https://buildopt-backend-production.up.railway.app/api/v1/ingest/status
```

Edge test (after edge agent running):
```bash
curl -X POST https://buildopt-backend-production.up.railway.app/api/v1/ingest/live \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_INGEST_API_KEY" \
  -d @sample-live.json
```

---

## What was built in code

| Component | Path |
|-----------|------|
| 30s poll pipeline (Influx + FDD + Supabase) | `app/services/pipeline.py` |
| Production live data layer | `app/services/live_data_service.py` |
| Edge ingest API | `POST /api/v1/ingest/live` |
| Building registry + Metasys mapping | `app/data/buildings_registry.py` |
| Edge gateway agent | `edge/agent.py` |
| Supabase migration | `supabase/migrations/001_building_alerts.sql` |

build-opt.site needs **no changes** — already connected to Railway.
