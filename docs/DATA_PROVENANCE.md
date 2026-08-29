# Data Provenance

BuildOpt operational data must be traceable. Live tenants must never receive data without knowing where it came from.

---

## Modes

| Mode | Source | UI behavior |
|------|--------|-------------|
| **DEMO** | SIMULATED, mock-data.ts, simulationEngine.ts | Demo badge visible |
| **LIVE** | METASYS, INFLUX, EDGE, IMPORT only | Empty/error if unavailable |

Mode resolution:
- Backend: `app/services/data_policy.py`
- Frontend: `src/lib/data-mode.ts` — Supabase session always live

---

## Provenance payload

Backend: `app/models/provenance.py`  
Frontend: `src/lib/data-source.ts` → `extractProvenance()`

---

## Live UI states

LIVE, STALE, OFFLINE, NOT_CONFIGURED, NO_DATA, PERMISSION_DENIED, API_ERROR, AUTH_ERROR, TIMEOUT

Component: `src/components/ui/DataStateBanner.tsx`

---

## Rules

1. LIVE API unavailable → typed error/empty — never mock fallback
2. Empty LIVE array stays empty
3. Missing LIVE metric → em dash or "No live data available"
4. Charts never merge mock series in LIVE mode
5. Production Supabase users cannot activate demo telemetry override

---

## Tests

- `tests/test_data_integrity.py`
- `src/test/data-source.test.ts`
