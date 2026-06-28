# BuildOpt production — completed setup log
# Generated: 2026-06-28

## Done automatically

- [x] Linked Railway project `buildopt-backend` (unique-expression)
- [x] Set Railway variables: DEMO_MODE, SECRET_KEY, INGEST_API_KEY, SUPABASE_URL, SUPABASE_KEY, CORS, GCC coords
- [x] Deployed latest code to Railway (`railway up`)
- [x] Verified `/api/v1/health` and `/api/v1/ingest/status`
- [x] Verified ingest API pushes live data (210 kW test)
- [x] Created `edge/.env` with matching INGEST_API_KEY

## One manual step remaining

**Supabase service role key** (cannot be read from frontend — secret):

1. Open https://supabase.com/dashboard/project/arddnpiluxrkndzzdpfi/settings/api
2. Copy **service_role** key (secret)
3. Railway → Variables → add:
   ```
   SUPABASE_SERVICE_KEY=<paste service_role key>
   ```
4. Supabase → SQL Editor → paste and run:
   `supabase/migrations/001_building_alerts.sql`

After that, FDD alerts from the pipeline will sync to Supabase.

## Railway URLs

- API: https://buildopt-backend-production.up.railway.app
- Docs: https://buildopt-backend-production.up.railway.app/docs
- Frontend: https://build-opt.site

## Ingest API key (also in Railway + edge/.env)

Store securely — required for edge gateway POST /api/v1/ingest/live

See Railway dashboard → buildopt-backend → Variables → INGEST_API_KEY

## Optional next

- InfluxDB Cloud token → Railway INFLUX_* vars
- Metasys creds → Railway JCI_* vars
- Set DEMO_MODE=false when real BMS data flows
