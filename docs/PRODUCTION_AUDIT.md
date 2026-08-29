# BuildOpt AI — Production Audit (OpenBlue Hardening)

**Date:** 2026-08-29  
**Prompt:** OpenBlue Competitive Hardening & Production Master  
**Phase:** 1 — Audit + demo/live separation

---

## Executive Summary

| Area | Status | Trust risk |
|------|--------|------------|
| Demo/live separation (backend) | **PARTIAL** | Module API fixed; global `DEMO_MODE` still defaults true |
| Demo/live separation (frontend) | **PARTIAL** | `pickApiOrMock` now strict in live; ~15 pages still import `mock-data` directly |
| Metasys connector | **PARTIAL** | `MetasysConnector` interface; no production E2E |
| Semantic model | **PARTIAL** | `canonical_points` migration; mapper pipeline incomplete |
| Data health | **PARTIAL** | Quality enums exist; no point-level aggregation yet |
| FDD | **PARTIAL** | Rule engine + NOT_EVALUABLE; no AHU rule pack on real points |
| Savings verification | **MISSING** | Potential vs verified not separated in UI |
| Write-back | **PASS (gated)** | READ_ONLY default; commands return 403 |
| LABS nav exposure | **PASS** | Hidden unless `VITE_ENABLE_LABS=true` or god mode |

---

## Page Inventory (~180 routes)

### CORE (production pilot scope)
| Route | Data source | Live safe? | Backend |
|-------|-------------|------------|---------|
| `/overview` | API + module data | PARTIAL | `/modules/overview/data` |
| `/portfolio` | mock + API | PARTIAL | `/buildings` |
| `/live-telemetry` | API/Influx | PARTIAL | `/buildings/{id}/live` |
| `/equipment` | API | PARTIAL | `/equipment` |
| `/integration-hub` | static + API | PARTIAL | `/health/connections` |
| `/tag-mapper` | Supabase + JCI API | PARTIAL | `/jci/buildings/{id}/objects` |
| `/data-health` | mock + API | PARTIAL | health endpoints |
| `/fdd-engine` | mock + API | PARTIAL | `/alerts/fdd` |
| `/optimization` | module API | PARTIAL | `/modules/optimization/data` |
| `/roi` | mock + energy API | PARTIAL | `/energy/savings` |
| `/reports` | mock | NO | partial |
| `/work-orders` | mock | NO | none |
| `/ai-chat-assistant` | LLM + mock | NO | none |
| `/settings`, `/bms-settings`, `/admin-console` | Supabase | YES | `/account/*`, `/admin/*` |

### ADVANCED (enabled in nav, not pilot-critical)
Digital Twin, What-If, Commissioning, Chiller Optimizer, Demand Response, IAQ, Carbon, Autonomous Control, Predictive Engine, Industrial Refrigeration, OpenBlue Bridge.

### LABS (hidden from default production nav)
Quantum Optimizer, Voice Twin, Carbon Trading/Marketplace, Sovereign LLM, Federated Learning, Agentic AI, Physics Twin, Twin Simulation, Insurance modules, Drone Fleet, Satellite EUI, etc.

Full tier map: `buildopt-ai/src/lib/module-tier.ts`

---

## Synthetic Data Entry Points (audit)

| Location | Risk | Mitigation |
|----------|------|------------|
| `buildopt-backend/app/services/demo_mode.py` | HIGH | Gated by `allows_simulated_telemetry()` |
| `buildopt-backend/app/services/module_data_service.py` | MEDIUM | Live empty state + provenance |
| `buildopt-ai/src/lib/mock-data.ts` | HIGH | Only used when `!isLiveDataMode()` on fixed pages |
| `buildopt-ai/src/lib/data-source.ts` | **FIXED** | Live never returns mock |
| `buildopt-ai/src/services/simulationEngine.ts` | MEDIUM | Disabled in live via `useLiveSimulation` |
| `pickApiOrMock` callers (~15 files) | MEDIUM | Now returns `null` in live — UI must handle |

---

## Duplicated / UI-only modules

- **OpenBlue Bridge** vs **Metasys Deep Link** — overlapping JCI story
- **FDD Engine** vs **Fault Prediction** vs **Predictive Engine** — three FDD surfaces
- **Digital Twin** vs **Physics Twin** vs **Twin Simulation** — LABS overlap
- **Work Orders** — UI mock, no backend WO API

---

## Security findings

| Issue | Severity | Status |
|-------|----------|--------|
| Global unauthenticated API (demo mode) | HIGH | PARTIAL — live routes require auth |
| localStorage demo override | MEDIUM | **FIXED** — blocked for Supabase sessions |
| Write-back stub success | HIGH | **FIXED** — 403 READ_ONLY |
| BMS credentials in browser | MEDIUM | Credentials saved via API only |
| Tenant isolation tests | HIGH | PARTIAL — `test_account_platform.py` |

---

## Remaining blockers

1. Real Metasys credentials (B1)
2. Railway `DEMO_MODE=false` + Influx configured (B2)
3. Direct `mock-data` imports on CORE pages (Phase 1 continue)

See also: `DATA_PROVENANCE.md`, `PILOT_READINESS.md`
