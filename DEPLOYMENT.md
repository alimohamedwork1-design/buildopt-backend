# Deploy BuildOpt Backend to Railway

## Prerequisites

- GitHub account
- [Railway](https://railway.app) account (free tier works for demo)
- This repo pushed to GitHub

## Step 1 — Push to GitHub

```powershell
cd "C:\Users\Ali Mohamed\Projects\buildopt-backend"

git add .
git commit -m "Add BuildOpt FastAPI backend with Railway deployment config"
git branch -M main

# Create a new repo on github.com named buildopt-backend, then:
git remote add origin https://github.com/YOUR_USERNAME/buildopt-backend.git
git push -u origin main
```

## Step 2 — Create Railway project

1. Go to [railway.app/new](https://railway.app/new)
2. Choose **Deploy from GitHub repo**
3. Select `buildopt-backend`
4. Railway detects `railway.toml` and builds with `Dockerfile.railway`

## Step 3 — Set environment variables

In Railway → your service → **Variables**, add:

| Variable | Value |
|----------|-------|
| `DEMO_MODE` | `true` |
| `APP_ENV` | `production` |
| `SECRET_KEY` | *(generate a random 32+ char string)* |
| `ALLOWED_ORIGINS` | `https://build-opt.site,https://www.build-opt.site,http://localhost:5173` |
| `TIMEZONE` | `Asia/Dubai` |
| `LATITUDE` | `25.2048` |
| `LONGITUDE` | `55.2708` |

Optional (only when moving off demo mode):

| Variable | When needed |
|----------|-------------|
| `INFLUX_URL`, `INFLUX_TOKEN`, `INFLUX_ORG`, `INFLUX_BUCKET` | Time-series storage |
| `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY` | Realtime alerts |
| `JCI_METASYS_HOST`, `JCI_METASYS_USERNAME`, `JCI_METASYS_PASSWORD` | Metasys integration |
| `BACNET_IP`, `MODBUS_HOST`, `MQTT_BROKER` | On-prem protocols |

## Step 4 — Generate public URL

1. Railway → service → **Settings → Networking**
2. Click **Generate Domain**
3. Copy the URL, e.g. `https://buildopt-backend-production.up.railway.app`

## Step 5 — Verify deployment

```powershell
curl https://YOUR-URL/api/v1/health
curl https://YOUR-URL/api/v1/buildings/burj-khalifa-01/live
```

Expected health response:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "demo_mode": true,
  "timestamp": "..."
}
```

Open `https://YOUR-URL/docs` for interactive API docs.

## Step 6 — Connect Lovable frontend

See [frontend-integration/LOVABLE_SETUP.md](./frontend-integration/LOVABLE_SETUP.md).

Quick version:

1. Lovable → Settings → Environment:
   - `VITE_API_URL` = your Railway URL
   - `VITE_DEMO_MODE` = `false`
2. Copy `frontend-integration/src/lib/api-client.ts` → `src/lib/api-client.ts`
3. Copy `frontend-integration/src/hooks/useBuildOptApi.ts` → `src/hooks/useBuildOptApi.ts`
4. Use the Lovable AI prompt from LOVABLE_SETUP.md to wire pages

## Troubleshooting

### Build fails (TensorFlow / BAC0)

Railway uses `Dockerfile.railway` + `requirements-railway.txt` (lightweight). Do not switch to the full `Dockerfile` unless you need BACnet/TensorFlow on-prem.

### CORS errors in browser

Add your exact frontend origin to `ALLOWED_ORIGINS`. Include Lovable preview URLs if testing there:

```
https://build-opt.site,https://www.build-opt.site,https://your-preview.lovable.app
```

### 502 / service not starting

Check Railway deploy logs. Ensure `PORT` is not hardcoded — the Dockerfile uses `${PORT:-8000}`.

### Health check failing

Railway hits `/api/v1/health`. Confirm the service is listening on `0.0.0.0`.

## Local vs Railway

| | Local (`docker compose`) | Railway |
|--|--------------------------|---------|
| Dockerfile | `Dockerfile` (full deps) | `Dockerfile.railway` (lean) |
| InfluxDB | Included in compose | Not included — use external or demo mode |
| Demo mode | `DEMO_MODE=true` | `DEMO_MODE=true` |

## Custom domain (optional)

Railway → Settings → Networking → Custom Domain → e.g. `api.build-opt.site`

Then set `VITE_API_URL=https://api.build-opt.site` in Lovable.
