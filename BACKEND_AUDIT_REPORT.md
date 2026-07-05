# BuildOpt AI — Backend Audit Report

**Date:** 2026-07-05  
**Railway URL:** `https://buildopt-backend-production.up.railway.app`  
**Auditor:** Cursor session (prompt v3, Task 1)

---

## Executive Summary

| Area | Status |
|------|--------|
| Route inventory | **71 API routes** registered under `/api/v1` (+ `GET /`) |
| JCI gap endpoints | **All present** — test-connection, save-credentials, network-diagnostic |
| Health “Data Health” quartet | **All present** — protocols, history, logs, pipeline |
| Live Railway verification | **PASS** — all probed endpoints respond with documented codes |
| Auth on building-data routes | **MISSING** — no Supabase JWT / user context on API today |
| Per-user demo vs live isolation | **MISSING** — global `DEMO_MODE` only (Tasks 2–7) |
| `POST /api/v1/buildings` (create) | **MISSING** — read-only building registry (Task 3) |
| `.env.example` drift | **FIXED** — added `PORT`, `TIMEZONE`, webhook vars |

**Production note:** Railway currently runs with `DEMO_MODE=true` (inferred from demo-shaped health/building responses). JCI endpoints perform real connection probes when called with credentials (`test-connection` always live; returns structured failure, not fake success).

---

## Live Verification (Railway)

Probed **2026-07-05** against `https://buildopt-backend-production.up.railway.app`.

| Method | Path | Code | Notes |
|--------|------|------|-------|
| GET | `/` | 200 | Returns `demo_mode: true` |
| GET | `/api/v1/health` | 200 | Railway healthcheck target |
| GET | `/api/v1/health/protocols` | 200 | Demo protocol cards when `DEMO_MODE=true` |
| GET | `/api/v1/health/history` | 200 | Demo time series when `DEMO_MODE=true` |
| GET | `/api/v1/health/logs` | 200 | Buffered + demo filler logs |
| GET | `/api/v1/health/pipeline` | 200 | Scheduler job tracker |
| GET | `/api/v1/health/connections` | 200 | Integration summary |
| POST | `/api/v1/jci/test-connection` | 422 | Empty body → validation error (expected) |
| POST | `/api/v1/jci/test-connection` | 200 | Valid body, invalid host → `{"status":"failed",...}` (not fake success) |
| POST | `/api/v1/jci/network-diagnostic` | 200 | Valid body → structured diagnostic with `overall: fail` |
| GET | `/api/v1/buildings` | 200 | Demo building list |
| GET | `/api/v1/energy/consumption?building_id=hq-tower` | 200 | Demo energy payload |
| GET | `/api/v1/equipment?building_id=hq-tower` | 200 | Demo equipment |
| GET | `/api/v1/alerts` | 200 | Demo alerts |
| GET | `/api/v1/ml/model-status` | 200 | Model registry status |
| GET | `/api/v1/protocols/status` | 200 | Protocol connectivity |
| GET | `/api/v1/modules` | 200 | Module registry |
| GET | `/api/v1/site/metadata` | 200 | Site metadata |
| GET | `/api/v1/gcc/prayer-times` | 200 | Prayer times |
| GET | `/api/v1/ingest/status` | 200 | Ingest status |
| GET | `/api/v1/sessions/stats` | 200 | Session stats |

**Task 1 verify:** **PASS** for known gap groups. No stubbed 200-with-fake-data on JCI probes.

---

## Full Route Inventory

Prefix for all API routes: **`/api/v1`**.  
**Auth column:** current state — almost all routes are **unauthenticated** (public).  
**DB column:** primary data source when `DEMO_MODE=false`.

| Method | Path | Auth | DB / Store | Status |
|--------|------|------|------------|--------|
| GET | `/` | none | none | working |
| GET | `/health` | none | Influx (live) / none (demo) | working |
| GET | `/health/connections` | none | Metasys/Influx/Supabase probes | working (demo when `DEMO_MODE=true`) |
| GET | `/health/protocols` | none | Influx + connection_store | working |
| GET | `/health/history` | none | Influx `api_health` | working |
| GET | `/health/logs` | none | in-memory log buffer | working |
| GET | `/health/pipeline` | none | pipeline_tracker | working |
| POST | `/health/alert-webhook/test` | none* | Supabase webhook | working (*secret in prod) |
| GET | `/buildings` | none | registry + demo_mode | working — **leaks demo data globally** |
| GET | `/buildings/{id}` | none | registry + demo_mode | working |
| GET | `/buildings/{id}/live` | none | Influx / demo_mode | working — 503 when live unavailable |
| GET | `/buildings/{id}/live/stream` | none | live_cache | working |
| GET | `/buildings/{id}/metrics` | none | Influx / demo | working |
| POST | `/buildings/{id}/control` | none | stub accept | **stubbed** — always `success: true` |
| GET/PUT | `/buildings/{id}/site-profile` | none | site_profile_store | working |
| GET | `/energy/consumption` | none | Influx / demo | working |
| GET | `/energy/forecast` | none | demo / ML | working |
| GET | `/energy/dewa-tariff` | none | computed | working |
| GET | `/energy/savings` | none | demo | working |
| GET | `/equipment` | none | demo / Metasys map | working |
| GET | `/equipment/{id}` | none | demo | working |
| GET | `/equipment/{id}/history` | none | Influx / demo | working |
| POST | `/equipment/{id}/setpoint` | none | JCI command | working (demo no-op) |
| GET | `/alerts` | none | Supabase / demo | working |
| GET | `/alerts/history` | none | Supabase / demo | working |
| POST | `/alerts/{id}/acknowledge` | none | Supabase | working |
| GET | `/alerts/fdd` | none | pipeline / demo | working |
| POST | `/ml/anomaly-detect` | none | ML service | working |
| POST | `/ml/forecast` | none | ML service | working |
| POST | `/ml/optimize` | none | ML service | working |
| GET | `/ml/model-status` | none | none | working |
| POST | `/jci/test-connection` | none | Metasys API | **working — live probe** |
| POST | `/jci/save-credentials` | none | Supabase `bms_connections` | working |
| POST | `/jci/network-diagnostic` | none | Metasys / DNS | working |
| POST | `/jci/auto-connect` | none | Metasys + mapper | working |
| GET/PUT | `/jci/buildings/{id}/objects` | none | metasys_object_store | working |
| POST | `/jci/buildings/{id}/objects/auto-map` | none | Metasys | working |
| GET | `/jci/logical-keys` | none | none | working |
| GET | `/jci/object-mappings` | none | store | working |
| GET | `/jci/objects` | none | Metasys | working |
| GET | `/jci/objects/{id}/present-value` | none | Metasys | working |
| POST | `/jci/objects/{id}/command` | none | Metasys | working |
| GET | `/jci/alarms` | none | Metasys | working |
| GET | `/jci/trends/{object_id}` | none | Metasys | working |
| GET/PUT/POST | `/refrigeration/buildings/{id}/*` | none | refrigeration stores | working |
| GET | `/refrigeration/snapshot/{id}` | none | Influx / demo | working |
| GET | `/gcc/prayer-times` | none | external API | working |
| GET | `/gcc/ramadan-mode` | none | computed | working |
| GET | `/gcc/sandstorm-alert` | none | computed | working |
| POST | `/gcc/hvac-prayer-adjust` | none | none | working |
| GET | `/protocols/status` | none | connection probes | working |
| POST | `/ingest/live` | **INGEST_API_KEY** | Influx | working |
| POST | `/ingest/heartbeat` | **INGEST_API_KEY** | none | working |
| GET | `/ingest/status` | none | none | working |
| GET | `/modules` | none | modules_registry | working |
| GET | `/modules/{slug}/data` | none | demo generators | working |
| GET | `/modules/categories` | none | registry | working |
| POST | `/sessions/events` | optional webhook secret | Supabase (optional) | working |
| GET | `/sessions/events` | none | in-memory | working |
| GET | `/sessions/stats` | none | in-memory | working |
| GET | `/site/metadata` | none | static | working |
| GET | `/site/config` | none | static | working |

---

## Known Gap Groups (Prompt v3)

### JCI V2 endpoints — **IMPLEMENTED**

| Endpoint | File | Behavior |
|----------|------|----------|
| `POST /jci/test-connection` | `app/api/jci.py:30` | Always `demo_mode=False`; returns connected/failed |
| `POST /jci/save-credentials` | `app/api/jci.py:49` | Validates live when `DEMO_MODE=false`; persists encrypted |
| `POST /jci/network-diagnostic` | `app/api/jci.py:80` | DNS/TLS/JWT/login checks |

### Health quartet — **IMPLEMENTED**

| Endpoint | File |
|----------|------|
| `GET /health/protocols` | `app/api/health.py:248` |
| `GET /health/history` | `app/api/health.py:276` |
| `GET /health/logs` | `app/api/health.py:310` |
| `GET /health/pipeline` | `app/api/health.py:385` |

---

## Fixes Applied (Task 1)

1. **`.env.example` updated** — added `PORT`, `TIMEZONE`, `SUPABASE_ALERT_WEBHOOK_URL`, `ALERT_WEBHOOK_SECRET` to match `app/config.py`.

---

## Critical Gaps for Tasks 2–7 (Not Yet Implemented)

| Task | Gap |
|------|-----|
| **2** | No `account_mode` on Supabase profiles; no per-user demo guard; backend serves demo data to all callers |
| **3** | No `POST /buildings`; buildings hardcoded in `BUILDING_REGISTRY` |
| **4** | No Excel import endpoint |
| **5** | No `feature_modules` / nav gating table or admin module APIs |
| **6** | No `require_admin` dependency; no `/admin/clients` routes |
| **7** | No `access_level` field or write guards |

**Blocker:** API has no Supabase JWT authentication layer. Tasks 2, 5, 6, 7 require `app/deps/auth.py` (Bearer token → user_id → profile/roles) before enforcement is meaningful.

---

## Environment Variables

Canonical reader: `app/config.py`.  
Reference files: `.env.example`, `railway.env.template`, `.env.production.example`.

| Variable | In `.env.example` | In `Settings` |
|----------|-------------------|---------------|
| `DEMO_MODE` | yes | yes |
| `PORT` | yes (fixed) | via `os.getenv` in `main.py` |
| `TIMEZONE` | yes (fixed) | yes |
| `SUPABASE_ALERT_WEBHOOK_URL` | yes (fixed) | yes |
| `ALERT_WEBHOOK_SECRET` | yes (fixed) | yes |

---

## Recommendations (Next Steps)

1. **Task 2** — Add Supabase migration `account_mode` + backend JWT auth + `require_live_account` dependency.
2. **Task 3** — `POST /buildings` + Supabase `buildings` table; decouple from static registry for live accounts.
3. Set Railway `DEMO_MODE=false` only after Task 2 guards are in place (avoid demo leak to real users).
4. Wire frontend `DemoModeToggle` to hide for `account_mode=live` users (not just `PROD` check).

---

## Task 1 Verdict

**PASS** — Route audit complete; JCI and health gap groups exist and respond correctly on Railway; `.env.example` drift fixed. No code stubs removed (none were broken). Structural gaps documented for Tasks 2–7.
