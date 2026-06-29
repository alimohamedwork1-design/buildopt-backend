# Backend coordination — alert webhook + incremental frontend rollout

Backend is ready. Two items need **Lovable** action; Railway needs **two env vars** once the edge function is live.

---

## Step 1 — Railway (you or dashboard)

After deploying the Supabase edge function (Step 2), set on Railway service `buildopt-backend`:

| Variable | Value |
|----------|-------|
| `SUPABASE_ALERT_WEBHOOK_URL` | `https://arddnpiluxrkndzzdpfi.supabase.co/functions/v1/sync-bms-alert` |
| `ALERT_WEBHOOK_SECRET` | `buildopt-alert-sync-2026-secret` |

**Must match** Lovable Cloud secret `BUILDOPT_WEBHOOK_SECRET` (same string).

Existing vars (keep as-is): `SUPABASE_URL`, `SUPABASE_KEY`, `DEMO_MODE=true`, etc.

---

## Step 2 — Lovable: deploy edge function

Paste **`frontend-integration/LOVABLE_EDGE_DEPLOY.md`** into Lovable chat (full function code + secrets checklist).

Creates:
- `supabase/functions/sync-bms-alert/index.ts`
- Secret `BUILDOPT_WEBHOOK_SECRET=buildopt-alert-sync-2026-secret`

Edge function writes to `building_alerts` (falls back to `alerts`).

---

## Step 3 — Verify webhook chain

After Railway redeploy + Lovable edge deploy:

```bash
BASE=https://buildopt-backend-production.up.railway.app

# Should show alert_webhook: true
curl $BASE/api/v1/health/connections

# Sends test alert → edge function → Supabase (skipped while DEMO_MODE=true)
curl -X POST $BASE/api/v1/health/alert-webhook/test
```

When `DEMO_MODE=false` and webhook is configured, test returns `"status": "ok"`.

---

## Step 4 — Lovable: incremental page rollout

Do **not** require all 172 pages in one pass. Paste **`frontend-integration/LOVABLE_INCREMENTAL_ROLLOUT.md`**.

Order:
1. Copy integration files (api client, hooks, `useModulePageData`, `data-source`, `BuildOptSessionSync`)
2. Wire priority pages first (`/`, `/telemetry`, `/fdd`, `/data-health`, `/system-status`)
3. Add `useModulePageData()` to remaining pages in batches — mocks stay as fallback

---

## Files to copy into Lovable repo

```
src/lib/buildopt-api.ts
src/lib/data-source.ts
src/hooks/useBuildOptApi.ts
src/hooks/useModulePageData.ts
src/components/BuildOptSessionSync.tsx
supabase/functions/sync-bms-alert/index.ts
```

Source: `frontend-integration/` in this repo.

---

## What backend already does

- FDD pipeline → `SupabaseService.push_alert()` → POST webhook with `x-buildopt-secret` header
- `/api/v1/modules/{slug}/data` serves all 172 pages
- V2 health endpoints for `/data-health` and `/system-status` pages
- `POST /api/v1/health/alert-webhook/test` for coordination verification

---

## Still optional (no blocker)

- `SUPABASE_SERVICE_KEY` on Railway — not required when using edge function webhook
- `DEMO_MODE=false` — only when real BMS hardware is connected
- Full 172-page rollout — incremental adoption is supported; mocks remain valid offline fallback
