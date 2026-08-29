# BuildOpt Productionization — Cursor Progress

**Last updated:** 2026-08-29  
**Prompt:** buildopt-cursor-master-productionization-prompt.md v1.0

---

## Phase Status (0–10)

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| **0** | Repository & production-readiness audit | **PASS** | `docs/production-readiness-audit.md` |
| **1** | Data integrity | **PARTIAL** | `data_policy.py`, `errors.py`, `module_data_service` live empty states, `test_data_integrity.py`; some pages still use `pickApiOrMock` |
| **2** | Auth, RBAC, tenant isolation | **PARTIAL** | `guards.py`, `UserContext`; not all routes scoped |
| **3** | Building onboarding & lifecycle | **PARTIAL** | `005_building_lifecycle.sql`, `excel_import.py`; no wizard / activate gate |
| **4** | Metasys REST integration | **PARTIAL** | `jci_metasys.py`, auto-mapper; no production E2E (B1) |
| **5** | Edge gateway & ingestion | **PARTIAL** | `edge/agent.py`, ingest API; BACnet live read placeholder |
| **6** | FDD rule engine | **PARTIAL** | 7 rules + `NOT_EVALUABLE`; demo injection when no faults |
| **7** | Write-back safety | **PARTIAL** | `READ_ONLY` default in `write_policy.py`; approval workflow planned |
| **8** | Documentation pack | **PASS** | 12 docs in `docs/` (this session) |
| **9** | Railway deployment hardening | **PARTIAL** | `requirements-railway.txt` updated (+openpyxl, multipart); scheduler lock still needed |
| **10** | Pilot go-live verification | **PARTIAL** | `production-verification.md`; `DEMO_MODE=true` on prod |

**Overall:** PARTIAL — demo-ready, not pilot-ready until blockers B1–B3 closed.

---

## Completed Phases

### PHASE 0 — Audit

**Status:** PASS

**Changed:**
- `docs/production-readiness-audit.md`
- `docs/cursor-progress.md`

**Verified:**
| Command | Result |
|---------|--------|
| `pytest tests/ -q` (backend) | **50 passed** |
| `npm test` (frontend) | 10 passed, 1 unhandled error |
| `npm run build` (frontend) | PASS |

---

### PHASE 8 — Documentation

**Status:** PASS

**Deliverables:**
- `docs/module-data-source-matrix.md`
- `docs/system-architecture.md`
- `docs/integration-architecture.md`
- `docs/metasys-integration.md`
- `docs/point-mapping.md`
- `docs/data-governance.md`
- `docs/security-model.md`
- `docs/fdd-rules.md`
- `docs/writeback-safety.md`
- `docs/railway-deployment.md`
- `docs/pilot-readiness-checklist.md`
- `docs/production-verification.md`
- `docs/cursor-progress.md` (updated)

**Verified:**
| Command | Result |
|---------|--------|
| `pytest tests/test_data_integrity.py tests/test_live_data_production.py tests/test_metasys_auto_mapper.py tests/test_health_v2.py -q` | 14 passed |

---

## Next Task

**PHASE 1 (continue) — Data integrity**

1. Replace remaining `pickApiOrMock` live fallbacks with `pickApiOrMockStrict` on priority pages
2. Wire `data_quality.py` into live API responses
3. Add full `DEMO_MODE=false` API matrix test
4. Add `openpyxl` + `python-multipart` to `requirements-railway.txt`

**Start command:**
```
Read docs/production-verification.md, then continue Phase 1 items 1–4.
```

---

## Unresolved Blockers

| ID | Description | Owner action |
|----|-------------|--------------|
| B1 | Real Metasys credentials/network | Provide pilot site access |
| B2 | Production InfluxDB + Supabase keys | Ops / Railway env |
| B3 | Destructive migration approval | Review before schema changes |

---

## Files Touched (cumulative)

### Phase 0
- `docs/production-readiness-audit.md`
- `docs/cursor-progress.md`

### Phase 1 (partial — code exists pre-doc session)
- `app/models/errors.py`
- `app/services/data_policy.py`
- `app/services/data_quality.py`
- `app/services/write_policy.py`
- `app/services/audit_log.py`
- `app/services/module_data_service.py`
- `app/services/live_data_service.py`
- `app/services/bms_connector.py`
- `app/ml/fault_detector.py`
- `tests/test_data_integrity.py`
- `buildopt-ai/src/lib/data-source.ts`

### Phase 8 — Documentation (this session)
- `docs/module-data-source-matrix.md`
- `docs/system-architecture.md`
- `docs/integration-architecture.md`
- `docs/metasys-integration.md`
- `docs/point-mapping.md`
- `docs/data-governance.md`
- `docs/security-model.md`
- `docs/fdd-rules.md`
- `docs/writeback-safety.md`
- `docs/railway-deployment.md`
- `docs/pilot-readiness-checklist.md`
- `docs/production-verification.md`
- `docs/cursor-progress.md`
