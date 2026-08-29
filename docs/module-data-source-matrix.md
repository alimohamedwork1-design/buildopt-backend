# Module Data Source Matrix

**Last updated:** 2026-08-29  
**Repos:** `buildopt-ai` (frontend) · `buildopt-backend` (API)

This matrix covers **priority pilot modules** and the universal module API pattern. ~172 routes exist; all unlisted slugs follow the same `/api/v1/modules/{slug}/data` contract defined in `app/data/modules_registry.py`.

## Legend

| Demo/Live behavior | Meaning |
|--------------------|---------|
| **Demo** | Seeded metrics from `app/services/demo_mode.py` or `useLiveSimulation` (14s cycle) |
| **Live empty** | `empty_state: true` when no telemetry (no silent mock) |
| **Live data** | Metasys poll → `live_cache` / InfluxDB → API |
| **Mock UI** | Page still reads `src/lib/mock-data.ts` directly |

## Priority modules

| Route | Frontend page | Data source | Demo / Live behavior | Backend endpoint | Status |
|-------|---------------|-------------|----------------------|------------------|--------|
| `/` | `src/pages/Overview.tsx` | Module API + live building | Demo: simulated KPIs · Live: empty or `get_live_data` | `GET /api/v1/modules/overview/data` | PARTIAL |
| `/telemetry` | `src/pages/LiveTelemetry.tsx` | Live cache / Influx | Live empty without BMS; demo shows HQ Tower points | `GET /api/v1/buildings/{id}/live` | PARTIAL |
| `/fdd` | `src/pages/FDDEngine.tsx` | FDD pipeline + module API | Demo: `demo_mode.list_fdd_results()` · Live: cached rule output or `NOT_EVALUABLE` | `GET /api/v1/alerts/fdd`, `GET /api/v1/modules/fdd/data` | PARTIAL |
| `/alerts` | Alert Intelligence page | Supabase + live cache | Demo alerts when `DEMO_MODE=true` | `GET /api/v1/alerts` | PARTIAL |
| `/equipment` | `src/pages/Equipment.tsx` | Live service / registry | Live: `[]` without mapping | `GET /api/v1/equipment` | PARTIAL |
| `/energy` | Energy modules | Live + DEWA tariff | Demo savings in demo mode | `GET /api/v1/energy/*` | PARTIAL |
| `/dewa-hub` | `src/pages/DewaHub.tsx` | GCC tariff service | Computed tariff (not versioned table) | `GET /api/v1/gcc/dewa-tariff` | PARTIAL |
| `/data-health` | `src/pages/DataHealth.tsx` | Health protocols API | Reflects real connector status when `demo_mode=false` | `GET /api/v1/health/protocols` | PARTIAL |
| `/system-status` | `src/pages/SystemStatus.tsx` | Pipeline tracker + health | Demo jobs seeded when `DEMO_MODE=true` | `GET /api/v1/health/pipeline` | PARTIAL |
| `/bms-settings` | `src/pages/BmsSettings.tsx` | JCI connection store | Connection test always hits real Metasys | `POST /api/v1/jci/test-connection`, `POST /api/v1/jci/save-credentials` | PARTIAL |
| `/tag-mapper` | Tag mapper UI | Metasys auto-mapper | Fuzzy map from discovered objects | `POST /api/v1/jci/buildings/{id}/objects/auto-map` | PARTIAL |
| `/setpoint-writeback` | Write-back UI | Metasys command API | **Blocked** — `WriteMode.READ_ONLY` default | `POST /api/v1/jci/objects/{id}/command` | PARTIAL |
| `/industrial-refrigeration` | Refrigeration module | Modbus/BACnet maps | Demo protocol stubs | `GET /api/v1/refrigeration/*` | PLACEHOLDER |
| `/asset-registry` | `src/pages/AssetRegistry.tsx` | Mock + module API | Mostly mock UI | `GET /api/v1/modules/asset-registry/data` | PLACEHOLDER |
| `/predictive` | `src/pages/PredictiveEngine.tsx` | Mock + ML API | Experimental sklearn/TF paths | `GET /api/v1/ml/status` | PLACEHOLDER |

## Universal module API (all other routes)

| Pattern | Value |
|---------|-------|
| Registry | `buildopt-backend/app/data/modules_registry.py` → `list_modules()` |
| Route map | `buildopt-ai/src/lib/nav-config.ts` (14 consolidated nav groups) |
| Hook | `buildopt-ai/src/hooks/useModuleFields.ts`, `frontend-integration/src/hooks/useModulePageData.ts` |
| Endpoint | `GET /api/v1/modules/{slug}/data?building_id=` |
| Policy | `app/services/data_policy.py` — live accounts get `_empty_live_payload()` when no telemetry |
| Frontend picker | `buildopt-ai/src/lib/data-source.ts` — use `pickApiOrMockStrict` in live mode |

## Category → typical data origin

| Category (`modules_registry`) | Primary backend source | Live prerequisite |
|------------------------------|------------------------|-------------------|
| `overview`, `telemetry` | `live_data_service.get_live_data` | Metasys map or edge ingest |
| `fault_prediction` | `pipeline.run_fdd_cycle` → `live_cache` | Mapped logical keys |
| `energy`, `financial` | Energy endpoints + module cards | Influx history / meters |
| `equipment` | `live_data_service.list_equipment` | Point mapping |
| `gcc` | `app/utils/gcc_features.py`, `dewa_tariff.py` | None (computed) |
| `jci` | `app/api/jci.py`, `connection_store` | Metasys REST reachable |
| `generic` | Module API seeded cards (demo only) | Category-specific telemetry |

## Frontend wiring status

| Integration layer | Path | Status |
|-------------------|------|--------|
| API client (reference) | `buildopt-backend/frontend-integration/src/lib/buildopt-api.ts` | COMPLETE |
| Live production client | `buildopt-ai/src/services/backendAPI.ts` | PARTIAL |
| Data mode guard | `buildopt-ai/src/lib/data-mode.ts` | PARTIAL |
| RBAC module list | `buildopt-ai/src/hooks/useAuth.tsx` → `roleConfig` | UI-only for many routes |

See `docs/system-architecture.md` for end-to-end flow.
