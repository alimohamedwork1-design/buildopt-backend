# BMS alert sync — SQL (no edge function)

Replaces `sync-bms-alert` edge function with a Postgres RPC.

## 1. Run SQL in Supabase

1. Open https://supabase.com/dashboard/project/arddnpiluxrkndzzdpfi/sql/new
2. Paste **`supabase/SYNC_BMS_ALERT.sql`** (full file in this repo)
3. Click **Run**

## 2. Railway (already set)

| Variable | Value |
|----------|--------|
| `SUPABASE_URL` | `https://arddnpiluxrkndzzdpfi.supabase.co` |
| `SUPABASE_KEY` | anon key (publishable) |
| `ALERT_WEBHOOK_SECRET` | `buildopt-alert-sync-2026-secret` |

`SUPABASE_ALERT_WEBHOOK_URL` is **optional** (legacy edge function only).

## 3. Verify

**In SQL Editor** (after step 1):

```sql
select public.sync_bms_alert(
  'buildopt-alert-sync-2026-secret',
  '{"id":"sql-smoke-1","building_id":"burj-khalifa-01","severity":"info","category":"test","title":"SQL test","message":"Hello"}'::jsonb
);
```

**From Railway** (when `DEMO_MODE=false`):

```bash
curl -X POST https://buildopt-backend-production.up.railway.app/api/v1/health/alert-webhook/test
```

Backend calls `POST /rest/v1/rpc/sync_bms_alert` with your anon key + secret.
