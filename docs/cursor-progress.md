# BuildOpt Productionization — Cursor Progress

**Last updated:** 2026-08-29  
**Prompts:** productionization master + OpenBlue competitive hardening (Phases 1–10)

---

## OpenBlue Hardening (Phases 1–10)

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| **1** | Live data integrity | **PASS** | `data-source.ts`, `data-mode.ts`, `module-tier.ts`, LABS nav gate, provenance |
| **2** | Metasys reliability | **PASS** | `http_retry.py`, retry on JCI reads, `RequestIdMiddleware` |
| **3** | Semantic mapper | **PASS** | `semantic_mapper.py` confidence thresholds (0.95 auto / 0.75 review) |
| **4** | Data health engine | **PASS** | `data_health_engine.py`, `GET /data-health/buildings/{id}`, `DataHealth.tsx` live-only |
| **5** | FDD rule expansion | **PASS** | 11 AHU/chiller/energy rules + `NOT_EVALUABLE` prerequisites |
| **6** | Savings engine | **PASS** | `savings_engine.py` POTENTIAL vs VERIFIED, `GET /savings/opportunities` |
| **7** | Recommendations lifecycle | **PASS** | `recommendations_store.py`, `GET /recommendations`, migration `006_*` |
| **8** | AI assistant tools | **PASS** | `ai_tools.py`, `POST /assistant/query` with evidence payload |
| **9** | Observability + tests | **PASS** | X-Request-ID, `test_openblue_services.py` — **65 pytest passed** |
| **10** | Control maturity + CORE mocks | **PARTIAL** | L0 default in `write_policy.py`; CORE pages: DataHealth, Equipment, LiveTelemetry, IntegrationHub fixed; ~20 ADVANCED/LABS pages still demo-first |

**Overall OpenBlue:** PARTIAL — architecture complete; pilot E2E blocked on B1–B3.

---

## Productionization Phases (0–10)

| Phase | Name | Status |
|-------|------|--------|
| **0** | Audit | **PASS** |
| **1** | Data integrity | **PASS** (CORE paths) |
| **2** | Auth / RBAC | **PARTIAL** |
| **3** | Building lifecycle | **PARTIAL** — self-contained migration `20260829120000_*` (re-run in Supabase) |
| **4** | Metasys REST | **PARTIAL** — retry + keepalive; no live E2E |
| **5** | Edge / ingest | **PARTIAL** |
| **6** | FDD | **PASS** (rule pack) |
| **7** | Write-back | **PASS** (READ_ONLY + L0–L4 maturity enum) |
| **8** | Documentation | **PASS** |
| **9** | Railway | **PARTIAL** |
| **10** | Pilot verification | **PARTIAL** |

---

## Verification (this session)

| Command | Result |
|---------|--------|
| `py -m pytest tests/ -q` (backend) | **65 passed** |
| `npm run build` (frontend) | **PASS** |
| `npm test -- src/test/data-source.test.ts` | **5 passed** |

---

## Unresolved Blockers

| ID | Description | Owner action |
|----|-------------|--------------|
| B1 | Real Metasys credentials/network | Provide pilot site access |
| B2 | Railway `DEMO_MODE=false` + InfluxDB | Ops env vars |
| B3 | Pilot building selection | Choose first live building |

---

## Next Steps

1. **Re-run** `buildopt-ai/supabase/migrations/20260829120000_building_lifecycle_canonical_points.sql` in Supabase SQL Editor (self-contained fix).
2. Apply `buildopt-backend/supabase/migrations/006_recommendations_savings.sql`.
3. Deploy backend with new routers (`/data-health`, `/savings`, `/recommendations`, `/assistant`).
4. Commit/push OpenBlue changes (exclude `AssetRegistry.tsx` / `PredictiveEngine.tsx` unless requested).
5. Remaining CORE pages (Alerts, Portfolio, ROI, Reports) — migrate to `pickApiArray` / `displayMetric` as needed.

---

## Key New Files (uncommitted)

### Backend
- `app/utils/http_retry.py`, `app/middleware/request_id.py`
- `app/services/semantic_mapper.py`, `data_health_engine.py`, `savings_engine.py`, `recommendations_store.py`, `ai_tools.py`
- `app/api/data_health.py`, `savings.py`, `recommendations.py`, `assistant.py`
- `supabase/migrations/006_recommendations_savings.sql`
- `tests/test_openblue_services.py`

### Frontend
- `src/lib/module-tier.ts`, updates to `data-source.ts`, `data-mode.ts`, `SidebarNav.tsx`
- `src/pages/DataHealth.tsx`, `Equipment.tsx`, `LiveTelemetry.tsx`, `IntegrationHub.tsx`
- `src/hooks/useBuildOptApi.ts`, `src/lib/api-client.ts` (data-health/savings/recommendations hooks)
