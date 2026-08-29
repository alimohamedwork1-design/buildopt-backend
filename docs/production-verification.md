# Production Verification

**Last updated:** 2026-08-29  
Command-level verification matrix for BuildOpt production stack.

**API base:** `https://buildopt-backend-production.up.railway.app/api/v1`  
**Frontend:** `https://build-opt.site`

## Summary table

| Check | Command | Result | Evidence | Risk |
|-------|---------|--------|----------|------|
| Backend health | `curl -s $API/health \| jq .status` | PASS (when deployed) | `status: "healthy"`, `health_score` present | LOW |
| Demo mode flag | `curl -s $API/health \| jq .demo_mode` | PASS (expected `true` pre-pilot) | `app/api/health.py` exposes flag | MEDIUM — must flip for live |
| Health connections | `curl -s $API/health/connections` | PARTIAL | influx/supabase/jci flags | HIGH if false in live |
| Protocol status | `curl -s $API/health/protocols` | PARTIAL | Simulated when `DEMO_MODE=true` | MEDIUM |
| Pipeline jobs | `curl -s $API/health/pipeline` | PASS | `fdd_engine`, `poll_building_data` jobs | MEDIUM — duplicate if scaled |
| Module API live empty | `pytest tests/test_data_integrity.py -q` | **PASS** (14 tests local) | `empty_state: true`, no random metrics | LOW |
| No silent demo fallback | `pytest tests/test_live_data_production.py -q` | **PASS** | `get_live_data` returns `None` | LOW |
| Metasys mapper | `pytest tests/test_metasys_auto_mapper.py -q` | **PASS** | Fuzzy mapping unit tests | LOW |
| Health v2 quartet | `pytest tests/test_health_v2.py -q` | **PASS** | Extended health endpoints | LOW |
| Ingest auth | `pytest tests/test_ingest_production.py -q` | **PASS** | Rejects missing API key | LOW |
| Excel import | `pytest tests/test_account_platform.py -q` | **FAIL** (local) | Missing `openpyxl` in venv | HIGH for onboarding |
| Site profile auth | `pytest tests/test_site_profile.py -q` | **FAIL** (local) | PUT returns 401 without JWT | LOW (expected) |
| Full backend suite | `pytest tests/ -q` | PARTIAL | 45+ pass, 2 fail (env gaps) | MEDIUM |
| Frontend unit tests | `cd buildopt-ai && npm test` | PARTIAL | 10 pass, 1 storage mock error | LOW |
| Frontend production build | `cd buildopt-ai && npm run build` | **PASS** | ~25s, chunk size warning | LOW perf |
| PowerShell verify script | `.\scripts\verify-production.ps1` | PARTIAL | `scripts/verify-production.ps1` | LOW |
| Metasys test-connection | `curl -X POST $API/jci/test-connection -H "Content-Type: application/json" -d '{...}'` | BLOCKED | Requires B1 credentials | HIGH |
| Live building data | `curl -s $API/buildings/{id}/live` | PARTIAL | Null/empty without BMS | HIGH |
| Ingest status | `curl -s $API/ingest/status` | PASS | Edge queue diagnostics | LOW |
| OpenAPI docs | `curl -s -o /dev/null -w "%{http_code}" $API/../docs` | PASS | `/docs` available | LOW |
| CORS preflight | Browser from `build-opt.site` | PASS | `main.py` Lovable regex | LOW |
| Write-back blocked | `POST $API/jci/objects/x/command` (READ_ONLY) | PARTIAL | `write_policy.py` — route wiring incomplete | **CRITICAL** |
| Supabase RLS | Manual cross-tenant query | NOT RUN | Needs staged test users | HIGH |
| Railway healthcheck | Railway dashboard deploy log | PASS | `railway.toml` 120s timeout | LOW |
| Edge heartbeat | `GET $API/health/protocols` after edge deploy | NOT RUN | Needs on-prem agent | MEDIUM |

## Commands reference

Set API for local runs:

```powershell
$API = "https://buildopt-backend-production.up.railway.app/api/v1"
```

### Backend tests (local)

```powershell
cd "C:\Users\Ali Mohamed\Projects\buildopt-backend"
.venv\Scripts\python.exe -m pytest tests/test_data_integrity.py tests/test_live_data_production.py tests/test_metasys_auto_mapper.py tests/test_health_v2.py -q
```

**Last run:** 14 passed, 1 warning (2026-08-29).

### Production smoke

```powershell
cd "C:\Users\Ali Mohamed\Projects\buildopt-backend"
.\scripts\verify-production.ps1
```

### Frontend

```powershell
cd "C:\Users\Ali Mohamed\Projects\buildopt-ai"
npm test
npm run build
```

### Metasys connection (when B1 closed)

```bash
curl -X POST "$API/jci/test-connection" \
  -H "Content-Type: application/json" \
  -d '{"host":"https://METASYS_HOST","username":"USER","password":"PASS","version":"v4"}'
```

**Pass:** `"status":"connected"`, `"object_count" > 0`.

### Live mode regression (critical)

```powershell
# With DEMO_MODE=false and no BMS:
$env:DEMO_MODE = "false"
pytest tests/test_data_integrity.py tests/test_live_data_production.py -q
```

**Pass:** No fabricated `metric_cards`, alerts, or equipment lists.

## Risk register (from verification)

| Risk | Severity | Mitigation |
|------|----------|------------|
| `DEMO_MODE=true` on production API | HIGH | Flip after B1–B2; verify health flag |
| Silent mock in `pickApiOrMock` (live) | HIGH | Migrate pages to `pickApiOrMockStrict` |
| Railway lean deps | HIGH | Add openpyxl, python-multipart to `requirements-railway.txt` |
| Unauthenticated Metasys probe | MEDIUM | Rate limit + auth |
| APScheduler multi-instance | MEDIUM | Single replica |
| Migration drift (4 vs 17 SQL files) | MEDIUM | Canonical path: `buildopt-ai/supabase/migrations` |
| Write command route not fully gated | CRITICAL | Wire `validate_write_request` before any write enable |

## Evidence artifacts

| Artifact | Path |
|----------|------|
| Phase 0 audit | `docs/production-readiness-audit.md` |
| Progress tracker | `docs/cursor-progress.md` |
| Pilot YAML checklist | `docs/pilot-readiness-checklist.md` |
| CI workflow | `.github/workflows/ci.yml` |

Re-run this matrix after each productionization phase and record dates in `cursor-progress.md`.
