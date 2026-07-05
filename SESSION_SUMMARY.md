# BuildOpt AI — Session Summary (Prompt v3)

**Date:** 2026-07-05  
**Scope:** Tasks 1–7 from `buildopt-cursor-prompt-v3.md`

---

## Task 1 — Backend Audit ✅

- Full route inventory in `BACKEND_AUDIT_REPORT.md`
- Live Railway verification passed for JCI + health gap groups
- `.env.example` synced with `app/config.py`

---

## Task 2 — Real Account Mode (No Demo Leakage) ✅

**Supabase migration:** `buildopt-ai/supabase/migrations/20260705120000_account_mode_buildings_modules.sql`
- `profiles.account_mode` enum: `demo` | `live` (default **live** for new users)
- `profiles.access_level` enum: `read_only` | `read_write`

**Backend:**
- `app/models/user_context.py` — `UserContext` with `allows_demo_data()`
- `app/deps/auth.py` — Supabase JWT → profile lookup
- `app/deps/guards.py` — `empty_no_building()`, `assert_building_access()`, `require_write_access`, `require_admin`
- Live accounts: empty building list, 404 empty payload (not zeros/mock)
- Energy, alerts, equipment, modules, buildings routes enforce account context

**Frontend:**
- JWT sent on all API requests in live mode (`api-client.ts`)
- `DemoModeToggle` hidden for `account_mode=live`
- `ConnectBuildingEmptyState` on Overview when live + zero buildings
- `useAccountProfile` / `useEnabledModules` hooks

---

## Task 3 — Add Building Flow ✅

- `POST /api/v1/buildings` — full metadata + optional encrypted credentials
- `POST /api/v1/buildings/{id}/test-connection` — separate from creation
- `app/services/building_store.py` — Supabase + in-memory fallback
- Tables: `buildings`, `building_connections`, `building_points`
- Influx queries scoped by `building_id` tag for live accounts

---

## Task 4 — Excel Upload ✅

- `POST /api/v1/buildings/{id}/import-excel` (`.xlsx`/`.xls`)
- `app/services/excel_import.py` — fuzzy header mapping, review report
- Dependencies: `openpyxl`, `python-multipart`

---

## Task 5 — Admin-Controlled Module Visibility ✅

- Table: `client_feature_modules` (account_id, optional building_id, module_slug, enabled)
- `GET/PUT /api/v1/admin/clients/{id}/modules`
- `GET /api/v1/account/modules` for frontend nav
- Server-side 403 on disabled modules (`/modules/{slug}/data`, energy, alerts, etc.)
- Frontend: `module-slugs.ts` + `SidebarNav` filtering

---

## Task 6 — Admin Cross-Client Visibility ✅

- `GET /api/v1/admin/clients`
- `GET /api/v1/admin/clients/{id}/buildings`
- `GET /api/v1/admin/clients/{id}/buildings/{building_id}/data`
- `require_admin` dependency (admin role in Supabase `user_roles`)

---

## Task 7 — Read-Only vs Read-Write ✅

- `profiles.access_level` column
- `PUT /api/v1/admin/clients/{id}/access-level`
- `require_write_access` on POST/PUT/DELETE mutating routes
- Frontend: `useIsReadOnlyAccount()` hook (wire to write controls as needed)

---

## Manual Steps for Aly

1. **Run Supabase migration** on production project:
   ```bash
   cd buildopt-ai
   supabase db push
   ```
   Or apply `20260705120000_account_mode_buildings_modules.sql` in Supabase SQL editor.

2. **Deploy backend** to Railway with updated deps (`openpyxl`, `python-multipart`).

3. **Verify env vars** on Railway:
   - `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY` (required for JWT profile lookup)
   - Keep `DEMO_MODE=true` until live accounts are tested; live users still get empty state via `account_mode`

4. **Do NOT set `DEMO_MODE=false` globally** until all live-account paths are verified — per-user `account_mode` is the primary gate.

5. **Test live account:** Sign up via Supabase → confirm Overview shows connect-building empty state (no KPI numbers).

6. **Test admin:** Use platform admin role → `GET /api/v1/admin/clients` with Bearer token.

---

## Still Open / Follow-Up

- Per-module write buttons can use `WriteGate` as modules are updated (backend enforcement is in place)
- Apply Supabase migration on production (`supabase db push`)
- Deploy backend to Railway with `openpyxl`, `python-multipart`
- Automated E2E test with real Supabase test project
- `DEMO_MODE=false` production cutover checklist in `PRODUCTION.md`

---

## Files Added/Changed (Key)

| Repo | Path |
|------|------|
| backend | `app/deps/`, `app/models/user_context.py`, `app/api/admin.py`, `app/api/account.py` |
| backend | `app/services/building_store.py`, `excel_import.py`, `account_service.py` |
| backend | `app/api/buildings.py` (POST, test-connection, import-excel) |
| backend | `tests/test_account_platform.py`, `SESSION_SUMMARY.md` |
| frontend | `supabase/migrations/20260705120000_*.sql` |
| frontend | `src/hooks/useAccountProfile.ts`, `src/components/ConnectBuildingEmptyState.tsx` |
| frontend | `src/lib/module-slugs.ts`, `Overview.tsx`, `SidebarNav.tsx`, `DemoModeToggle.tsx` |

---

## Verification

- Frontend: `npm run build` ✅
- Backend: `pytest tests/test_account_platform.py tests/test_api.py` ✅ (after `python-multipart` install)
