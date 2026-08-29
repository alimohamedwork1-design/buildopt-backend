# Railway Deployment

**Last updated:** 2026-08-29  
Deploy `buildopt-backend` to Railway with healthcheck and production env vars.

## Prerequisites

- GitHub repo: `buildopt-backend`
- [Railway](https://railway.app) account
- Domain (optional): custom API domain or Railway-generated `*.up.railway.app`

## Deploy steps

### 1. Connect repository

1. Railway → **New Project** → Deploy from GitHub
2. Select `buildopt-backend`
3. Railway reads `railway.toml`:

```toml
# railway.toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile.railway"

[deploy]
healthcheckPath = "/api/v1/health"
healthcheckTimeout = 120
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
```

### 2. Build image

`Dockerfile.railway` installs lean deps from `requirements-railway.txt` and starts:

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Known gap:** Lean deps omit `openpyxl`, `python-multipart`, `BAC0` — Excel import and multipart upload fail until added or feature-gated.

### 3. Set environment variables

Copy from `railway.env.template`. **Do not commit secrets.**

| Variable | Required | Description |
|----------|----------|-------------|
| `DEMO_MODE` | Yes | `true` for demo; `false` for live pilot |
| `APP_ENV` | Yes | `production` |
| `SECRET_KEY` | Yes | `openssl rand -hex 32` |
| `ALLOWED_ORIGINS` | Yes | `https://build-opt.site,https://www.build-opt.site` |
| `POLL_INTERVAL_SECONDS` | No | Default `30` |
| `INGEST_API_KEY` | Prod | Shared secret for edge ingest (warned if unset) |
| `SUPABASE_URL` | Live | Supabase project URL |
| `SUPABASE_KEY` | Live | Anon key |
| `SUPABASE_SERVICE_KEY` | Live | Service role (server only) |
| `INFLUX_URL` | Live | InfluxDB Cloud URL |
| `INFLUX_TOKEN` | Live | Read/write token |
| `INFLUX_ORG` | Live | e.g. `buildopt` |
| `INFLUX_BUCKET` | Live | e.g. `building_metrics` |
| `JCI_METASYS_HOST` | Optional | HTTPS Metasys base URL |
| `JCI_METASYS_USERNAME` | Optional | API user |
| `JCI_METASYS_PASSWORD` | Optional | API password |
| `JCI_METASYS_VERSION` | Optional | `v4` |
| `TIMEZONE` | No | `Asia/Dubai` |
| `LATITUDE` / `LONGITUDE` | No | GCC prayer/sandstorm features |
| `SUPABASE_ALERT_WEBHOOK_URL` | Recommended | FDD → edge function |

**Not on Railway:** `BACNET_IP`, `MODBUS_HOST` — edge gateway only (`edge/.env`).

### 4. Generate public URL

Railway → Service → **Settings → Networking → Generate Domain**

Example: `https://buildopt-backend-production.up.railway.app`

### 5. Connect frontend

`buildopt-ai` environment:

```
VITE_API_URL=https://buildopt-backend-production.up.railway.app
VITE_DEMO_MODE=false
VITE_SUPABASE_URL=<project>
VITE_SUPABASE_PUBLISHABLE_KEY=<anon>
```

See `LOVABLE_CONNECT.md`, `DEPLOYMENT.md`.

### 6. Apply Supabase migrations

Migrations are **manual** — not run on Railway deploy.

```powershell
# Canonical migrations in buildopt-ai
cd buildopt-ai/supabase
supabase db push

# Or backend mirror scripts
cd buildopt-backend
python scripts/apply_supabase_migration.py
python scripts/verify_supabase_tables.py
```

## Healthcheck

| Check | URL | Pass |
|-------|-----|------|
| Liveness | `GET /api/v1/health` | `status: "healthy"` |
| Connections | `GET /api/v1/health/connections` | influx/supabase flags |
| Protocols | `GET /api/v1/health/protocols` | Metasys/edge status |
| Pipeline | `GET /api/v1/health/pipeline` | Scheduler jobs running |
| Root | `GET /` | `demo_mode` field present |

Railway waits up to **120s** on first deploy for healthcheck.

### Verify script

```powershell
cd buildopt-backend
.\scripts\verify-production.ps1
```

## CI

`.github/workflows/ci.yml` — runs pytest on push (local venv may need full `requirements.txt`).

## Operational risks

| Risk | Mitigation |
|------|------------|
| APScheduler duplicate on scale-out | Keep single Railway replica until Redis lock |
| Lean Docker deps | Align `requirements-railway.txt` with pilot features |
| Migration drift | Single canonical migration path (`buildopt-ai`) |
| `DEMO_MODE=true` in prod | Flip only after Phase 1–3 verification |

## Related docs

- `DEPLOYMENT.md` — step-by-step with PowerShell
- `PRODUCTION.md` — demo → live cutover phases
- `scripts/PRODUCTION_ENV.md`
- `docs/production-verification.md`
