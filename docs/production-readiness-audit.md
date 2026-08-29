# BuildOpt AI — Production Readiness Audit

**Version:** 1.0  
**Date:** 2026-08-29  
**Phase:** 0 — Repository & Production-Readiness Audit  
**Auditor:** Cursor agent (master productionization prompt v1.0)

---

## Executive Summary

BuildOpt AI spans **two repositories**:

| Repository | Role | Maturity |
|------------|------|----------|
| `buildopt-ai` | React 18 / TypeScript / Vite frontend (~180 module pages) | **Mature UI**, demo-first data wiring |
| `buildopt-backend` | Python FastAPI V2 API, ingestion, BMS adapters, ML/FDD | **Partially implemented**, Railway-deployed |

**Overall status: PARTIAL — strong demo platform, not yet pilot-ready for live tenants.**

Critical gaps before a real building pilot:

1. **Global `DEMO_MODE=true` default** on backend; simulated telemetry can leak to unauthenticated callers.
2. **`module_data_service.py`** generates seeded random metrics for all 172 modules even when live telemetry is absent.
3. **Frontend `pickApiOrMock` / `mock-data.ts`** silently fills charts on many pages when API returns empty.
4. **No end-to-end production-proven Metasys ingestion** to InfluxDB for a live tenant building.
5. **Tenant isolation partially implemented** — `UserContext` + guards exist, but many routes remain globally accessible.
6. **Supabase schema split** — 17 migrations in frontend repo vs 4 in backend repo (drift risk).
7. **Railway lean deps** (`requirements-railway.txt`) omit `openpyxl`, `python-multipart`, BAC0 — breaks Excel import and file upload in prod image unless fixed.

---

## Repository Inventory

### Frontend (`buildopt-ai`)

```
buildopt-ai/
├── src/
│   ├── pages/           # ~180 lazy-loaded module pages
│   ├── components/      # shadcn/ui, layout shell, BMS panels
│   ├── hooks/           # useAuth, useLiveData, useModuleFields, useLiveSimulation
│   ├── services/        # buildingAPI, backendAPI, jciAPI, simulationEngine
│   ├── lib/             # mock-data, data-mode, nav-config, api-client
│   └── integrations/supabase/  # client + auto-generated types (DO NOT EDIT)
├── supabase/
│   ├── migrations/      # 17 SQL migrations (auth, RLS, buildings, modules)
│   └── functions/       # edge functions
├── scripts/             # audit-modules, i18n, migration helpers
└── package.json         # vite, vitest, eslint
```

### Backend (`buildopt-backend`)

```
buildopt-backend/
├── app/
│   ├── api/             # 15 route modules (account, admin, alerts, buildings, energy, …)
│   ├── services/        # live_data, demo_mode, jci_metasys, influx, pipeline, …
│   ├── ml/              # fault_detector, anomaly_detector, lstm, mpc
│   ├── deps/            # auth.py, guards.py
│   ├── models/          # schemas, user_context, db_models
│   └── data/            # buildings_registry, modules_registry, static JSON maps
├── edge/                # on-prem BACnet agent + docker-compose
├── supabase/migrations/ # 4 SQL files (alerts, bms_connections — subset of frontend)
├── tests/               # 14 test modules
├── frontend-integration/ # Lovable wiring prompts + reference hooks
├── railway.toml         # Docker deploy, healthcheck /api/v1/health
├── requirements.txt     # full stack (BAC0, TensorFlow, openpyxl, …)
└── requirements-railway.txt  # lean prod image (no BAC0/TF/openpyxl/multipart)
```

### Deployment & Config

| Asset | Path | Status |
|-------|------|--------|
| Railway config | `railway.toml`, `Dockerfile.railway` | COMPLETE |
| Docker Compose (local) | `docker-compose.yml` | COMPLETE |
| Edge agent | `edge/agent.py`, `edge/DEPLOY.md` | PARTIAL |
| Env templates | `.env.example`, `railway.env.template` | PARTIAL — missing `cryptography` key derivation note |
| CI | `.github/workflows/ci.yml` | PRESENT |
| Docs folder | `docs/` | **CREATED** (this audit) |

---

## Verification Evidence (Phase 0)

| Check | Command | Result | Notes |
|-------|---------|--------|-------|
| Backend tests | `pytest tests/ -q` | **45 passed, 2 failed** | Failures: missing `openpyxl` in local venv; site-profile PUT returns 401 (auth now required) |
| Backend import | `from app.main import app` | PASS (after `cryptography`, `python-multipart` install) | Local venv incomplete vs `requirements.txt` |
| Frontend tests | `npm test` | **10 passed**, 1 unhandled rejection | Supabase storage mock missing in `auth-guard.test.tsx` |
| Frontend build | `npm run build` | **PASS** (25.6s) | Main chunk 2.7MB — performance risk |
| Frontend lint | Not run | — | Deferred to Phase 10 |
| Railway health | Prior audit 2026-07-05 | PASS | `demo_mode: true` on production URL |

---

## Data Integrity Audit

### Policy State

| Layer | Mechanism | Status |
|-------|-----------|--------|
| Backend global | `DEMO_MODE` env (`config.py`, default **true**) | PARTIAL — single flag, not per-tenant |
| Backend per-user | `UserContext.account_mode`, `allows_demo_data()` | PARTIAL — wired on some routes |
| Frontend | `src/lib/data-mode.ts` — `isLiveDataMode()`, localStorage override | PARTIAL — client-side, can be bypassed |
| Frontend fallback | `src/lib/data-source.ts` — `pickApiOrMock`, `pickApiArray` | **RISK** — silent mock fallback in live mode when API empty |

### High-Risk Runtime Data Sources

| File | Pattern | Risk | Action |
|------|---------|------|--------|
| `app/services/demo_mode.py` | `random`, seeded fake buildings/telemetry | HIGH in live | Gate entirely behind `DEMO_MODE` + `allows_demo_data()` — partially done |
| `app/services/module_data_service.py` | `_seed()`, `_metric_cards()` random | **CRITICAL** | Live accounts get fabricated module KPIs when no telemetry |
| `app/services/live_data_service.py` | Falls back to demo savings/alerts in live list | HIGH | Lines 75–78 use demo values for savings/alerts |
| `src/lib/mock-data.ts` | 62 mock references | HIGH | Used by most pages directly or via hooks |
| `src/services/simulationEngine.ts` | 14s live simulation cycle | MEDIUM | OK in demo; must not run in live |
| `src/hooks/useLiveSimulation.ts` | Periodic mock refresh | MEDIUM | Used by ModuleShell — needs live guard |
| `src/lib/data-source.ts` | `pickApiOrMock` | **CRITICAL** | Returns mock when API value null/empty in live mode |
| `app/ml/fault_detector.py` | Demo random faults when `demo_mode=True` | MEDIUM | Rule engine exists; needs prerequisite checks |
| `app/services/bacnet_client.py` | Returns `0.0` in demo | LOW | Expected stub |
| `app/services/modbus_client.py` | Demo values | LOW | Expected stub |
| `app/services/mqtt_client.py` | Demo values | LOW | Expected stub |

### Frontend Mock/Demo Surface Area

Grep counts in `buildopt-ai/src` for integrity keywords: **~170 files** touched.

Pages using `useLiveSimulation` or `Math.random`: **~40 files** — includes FDDEngine, DigitalTwin, VoiceTwin, etc.

Central mock entry points:

- `src/lib/mock-data.ts` — primary HQ Tower demo dataset
- `src/lib/mock-data-advanced.ts` — extended scenarios
- `src/services/simulationEngine.ts` — 14s cycle matching backend demo ranges
- `src/hooks/useModuleFields.ts` — merges API + mock fields for ModuleShell pages

**Recommendation (Phase 1):** Introduce centralized `DataPolicy` service on both sides; remove silent `pickApiOrMock` fallback in live mode; return typed empty/error states instead.

---

## Feature Audit Matrix

Status key: **COMPLETE** | **PARTIAL** | **PLACEHOLDER** | **BROKEN** | **MISSING**

### Core Platform

| Feature | Path(s) | Status | Risk | Recommended Action |
|---------|---------|--------|------|-------------------|
| FastAPI app + lifespan | `app/main.py` | COMPLETE | LOW | Add multi-instance scheduler lock |
| APScheduler jobs | `app/services/pipeline.py` | PARTIAL | HIGH | Duplicate jobs on Railway scale-out |
| Health endpoints | `app/api/health.py` | COMPLETE | LOW | Separate liveness/readiness |
| CORS | `app/main.py` | COMPLETE | MEDIUM | Review origin regex |
| Structured logging | `app/services/log_handler.py` | PARTIAL | MEDIUM | Add correlation IDs |
| `.env.example` | `.env.example` | PARTIAL | LOW | Add all vars; remove real Supabase URL |

### Authentication & RBAC

| Feature | Path(s) | Status | Risk | Recommended Action |
|---------|---------|--------|------|-------------------|
| Supabase JWT validation | `app/deps/auth.py`, `account_service.py` | PARTIAL | HIGH | Not enforced on all routes |
| UserContext | `app/models/user_context.py` | PARTIAL | MEDIUM | Expand role granularity |
| Route guards | `app/deps/guards.py` | PARTIAL | HIGH | Apply to energy, equipment, modules |
| Frontend RBAC | `src/hooks/useAuth.tsx` | PARTIAL | HIGH | UI-only for many modules |
| Supabase RLS | `buildopt-ai/supabase/migrations/*` | PARTIAL | HIGH | Audit cross-tenant policies |
| Platform admin | migrations `platform_admin_role` | PARTIAL | MEDIUM | Verify server-side admin checks |
| Demo quick-login | `src/hooks/useDemoAuth.tsx` | COMPLETE | MEDIUM | Disabled in prod when `VITE_DEMO_MODE=false` |

### Multi-Tenant Domain Model

| Entity | Backend | Supabase (frontend migrations) | Status |
|--------|---------|-------------------------------|--------|
| Organization/Client | via `profiles` | `profiles.account_mode` | PARTIAL |
| Building | `building_store.py`, `buildings` API | `public.buildings` | PARTIAL |
| Building connection | `connection_store.py` | `building_connections` | PARTIAL |
| Points | `excel_import.py`, `building_points` | `public.building_points` | PARTIAL |
| Systems/Equipment | demo registry | JSONB `systems` on buildings | PLACEHOLDER |
| Canonical point model | metasys/refrigeration maps | metadata jsonb only | PARTIAL |
| Module entitlements | `modules_registry.py` | `client_feature_modules` | PARTIAL |

### Building Onboarding

| Stage | Path | Status | Notes |
|-------|------|--------|-------|
| Basic info CRUD | `POST /buildings`, `building_store.py` | PARTIAL | Create exists; no full wizard UI |
| BMS credentials | `POST /jci/save-credentials` | PARTIAL | Encrypted in Supabase |
| Connection test | `POST /jci/test-connection` | COMPLETE | Real probe, structured failure |
| Excel/CSV import | `excel_import.py`, upload route | PARTIAL | openpyxl missing on Railway image |
| Point mapping | `metasys_auto_mapper.py` | PARTIAL | Fuzzy matching tested |
| Building states | — | **MISSING** | No DRAFT→ACTIVE state machine |
| Activate building | — | **MISSING** | Form submit ≠ active |

### BMS Connectors

| Protocol | Path | Status | Evidence |
|----------|------|--------|----------|
| Metasys REST | `app/services/jci_metasys.py` | PARTIAL | Real HTTP login/read; demo token path |
| Metasys auto-mapper | `metasys_auto_mapper.py` | PARTIAL | Unit tests pass |
| BACnet | `bacnet_client.py`, `edge/agent.py` | PLACEHOLDER | BAC0 in full requirements only |
| Modbus TCP | `modbus_client.py` | PLACEHOLDER | Demo/simulated reads |
| MQTT | `mqtt_client.py` | PLACEHOLDER | Demo/simulated |
| OPC-UA | — | **MISSING** | Not implemented |
| Cloudflare Tunnel | `edge/DEPLOY.md` | PARTIAL | Documented, not automated |

### Ingestion & Storage

| Component | Path | Status | Notes |
|-----------|------|--------|-------|
| Poll cycle | `pipeline.run_poll_cycle` | PARTIAL | Metasys poll when configured |
| Edge ingest | `POST /ingest/live` | COMPLETE | API key protected |
| InfluxDB client | `influx_client.py` | PARTIAL | Demo mode skips writes |
| Live cache | `live_cache.py` | COMPLETE | In-memory latest |
| Data quality engine | — | **MISSING** | No GOOD/STALE/INVALID states |
| Provenance tagging | — | **MISSING** | `demo_mode` flag only |

### API V2 Endpoints

~71 routes under `/api/v1` (per prior `BACKEND_AUDIT_REPORT.md`).

| Group | Auth enforced | Live-data safe | Status |
|-------|---------------|----------------|--------|
| `/buildings` | PARTIAL | PARTIAL | Live user path uses Supabase rows |
| `/energy`, `/equipment`, `/alerts` | MINIMAL | PARTIAL | Global demo when `DEMO_MODE=true` |
| `/jci/*` | MINIMAL | COMPLETE | Connection tests always real |
| `/modules/{slug}/data` | MINIMAL | **BROKEN for live** | Random metrics always appended |
| `/ingest/*` | API key | COMPLETE | — |
| `/admin`, `/account` | PARTIAL | PARTIAL | Newer routes |

Typed errors (`DEMO_DATA_FORBIDDEN`, etc.): **MISSING** as structured error codes.

### FDD & ML

| Component | Path | Status | Notes |
|-----------|------|--------|-------|
| Rule-based FDD | `ml/fault_detector.py` | PARTIAL | 26 rules; no NOT_EVALUABLE state |
| FDD pipeline job | `pipeline.run_fdd_cycle` | PARTIAL | Runs on cached/demo readings |
| Anomaly (sklearn) | `ml/anomaly_detector.py` | EXPERIMENTAL | Not validated |
| LSTM / MPC | `ml/lstm_predictor.py`, `mpc_optimizer.py` | PLANNED | TensorFlow in full deps only |
| ML API | `api/ml.py` | PARTIAL | Returns model status; demo inference |

### Frontend Modules

| Metric | Value |
|--------|-------|
| Total routes/pages | ~180 |
| Nav groups | 14 consolidated |
| Wired to Railway API | ~6 specialized + universal `/modules/{slug}/data` |
| Mock-only pages | Majority use `mock-data` or `useLiveSimulation` |
| Live telemetry page | `LiveTelemetry.tsx` — PARTIAL |
| BMS settings | `BmsSettings.tsx`, Metasys panels — PARTIAL |
| Demo badge | `DemoDataBadge.tsx` — COMPLETE |

### GCC / UAE Features

| Feature | Path | Status |
|---------|------|--------|
| DEWA tariff | `utils/dewa_tariff.py` | PARTIAL — computed, not versioned table |
| Prayer times | `gcc_features.py`, `/gcc/prayer-times` | COMPLETE |
| Ramadan mode | `/gcc/ramadan-mode` | PARTIAL |
| Sandstorm alert | `/gcc/sandstorm-alert` | PARTIAL |
| Arabic RTL | frontend i18n | COMPLETE |
| AED costs | energy endpoints | PARTIAL |

### Write-Back / Control

| Feature | Path | Status | Risk |
|---------|------|--------|------|
| Building control | `POST /buildings/{id}/control` | PLACEHOLDER | Returns success stub |
| Equipment setpoint | `POST /equipment/{id}/setpoint` | PARTIAL | Metasys command when live |
| JCI object command | `POST /jci/objects/{id}/command` | PARTIAL | No approval workflow |
| Write policy modes | — | **MISSING** | No READ_ONLY default enforcement |
| Audit trail | — | **MISSING** | — |

### Observability & Security

| Item | Status | Notes |
|------|--------|-------|
| Health check | COMPLETE | Railway uses `/api/v1/health` |
| Request correlation IDs | MISSING | — |
| Secret logging audit | PARTIAL | Credentials excluded from logs |
| Rate limiting | MISSING | — |
| SSRF on integration URLs | PARTIAL | Metasys host user-configurable |
| Cross-tenant tests | PARTIAL | `test_account_platform.py` exists |
| PDPL / data governance doc | MISSING | Required in Phase 10 |

---

## Duplicate / Dead Code

| Item | Location | Notes |
|------|----------|-------|
| Supabase migrations | frontend vs backend repos | **Duplicate/drift** — canonical should be frontend repo |
| Demo building IDs | `demo_mode.py` vs `buildings_registry.py` | Different ID sets (burj-khalifa vs hq-tower) |
| Integration docs | `BACKEND_AUDIT_REPORT.md`, `PRODUCTION_STATUS.md`, `frontend-integration/*` | Overlap — consolidate into `docs/` |
| `frontend-integration/src/*` | Reference copies | Not the live frontend; sync manually |

---

## Environment Variables

### Backend (critical)

| Variable | Default | Production concern |
|----------|---------|-------------------|
| `DEMO_MODE` | `true` | **Must be false for live tenants** |
| `INGEST_API_KEY` | empty | Warned in prod startup if unset |
| `SECRET_KEY` | `change-me-in-production` | Must rotate |
| `SUPABASE_*` | empty | Required for live accounts |
| `INFLUX_*` | localhost defaults | Required for telemetry persistence |
| `JCI_METASYS_*` | empty | Per-building creds in Supabase preferred |

### Frontend (critical)

| Variable | Purpose |
|----------|---------|
| `VITE_API_URL` | Railway backend |
| `VITE_DEMO_MODE` | `false` for production live |
| `VITE_ALLOW_DEMO_LOGIN` | Disable in prod |
| `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` | Auth |

---

## Test Coverage Summary

### Backend (`tests/`)

| Module | Focus | Status |
|--------|-------|--------|
| `test_live_data_production.py` | No silent demo fallback | PASS |
| `test_ingest_production.py` | Ingest auth | PASS |
| `test_metasys_auto_mapper.py` | Point mapping | PASS |
| `test_protocols.py` | Protocol status | PASS |
| `test_account_platform.py` | Excel import | **FAIL** (openpyxl) |
| `test_site_profile.py` | Site profile API | **FAIL** (401 on PUT) |
| `test_health_v2.py` | Health quartet | PASS |
| `test_webhook_coordination.py` | Alert webhook | PASS |

### Frontend (`src/test/`)

| Test | Status |
|------|--------|
| `data-mode.test.ts` | PASS |
| `module-content-registry.test.ts` | PASS |
| `module-shell.test.tsx` | PASS |
| `auth-guard.test.tsx` | Unhandled Supabase storage error |

### Critical Missing Test

> Set `DEMO_MODE=false`, remove BMS config, hit all major dashboard APIs — **must return zero simulated operational values.**

Partial coverage exists in `test_live_data_production.py`; full matrix not yet implemented.

---

## Deployment Audit (Railway)

| Check | Status | Finding |
|-------|--------|---------|
| Start command | OK | Uvicorn via Dockerfile.railway |
| Healthcheck | OK | `/api/v1/health`, 120s timeout |
| Python deps | **RISK** | `requirements-railway.txt` missing openpyxl, python-multipart, BAC0 |
| Scheduler | **RISK** | In-process APScheduler — no distributed lock |
| Migrations | **RISK** | Manual Supabase apply; no automated migration on deploy |
| CORS | OK | build-opt.site + Lovable regex |
| Secrets in repo | **FLAG** | `.env.example` contains real Supabase project URL |

---

## Phase 0 Conclusion

### Status: **PARTIAL**

### Changed (this session)

- `docs/production-readiness-audit.md` (this file)
- `docs/cursor-progress.md` (progress tracker)

### Verified

- Backend pytest: 45/47 pass (local venv gaps)
- Frontend vitest: 10/10 pass (+ 1 env error)
- Frontend production build: PASS

### Remaining (Phase 1+)

1. Centralize DEMO/LIVE data policy; eliminate silent mock fallback
2. Fix `module_data_service` live-account random metrics
3. Align Railway dependencies with `requirements.txt` features
4. Complete tenant-scoped auth on all data routes
5. Implement building lifecycle states + onboarding wizard
6. Prove Metasys → InfluxDB → UI path with real credentials
7. Add typed error envelopes
8. Create remaining deliverable docs (module matrix, architecture, pilot checklist)

### Blockers

| ID | Blocker | Input needed |
|----|---------|--------------|
| B1 | Real Metasys integration test | Customer network credentials + tunnel |
| B2 | Production Supabase/Influx credentials | Ops provisioning |
| B3 | Pilot building selection | Client/JCI partner decision |

---

## Recommended Implementation Order

Proceed per master prompt Phases 1–10. Next immediate task:

**Phase 1 — Data integrity:** Refactor `module_data_service`, `data-source.ts`, and `live_data_service` demo fallbacks; add typed errors; frontend honest empty states.

See `docs/cursor-progress.md` for session continuity.
