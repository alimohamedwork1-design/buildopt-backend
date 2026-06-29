# Deploy sync-bms-alert edge function

## 1. Supabase Dashboard

1. Open [Supabase project](https://supabase.com/dashboard/project/arddnpiluxrkndzzdpfi/functions)
2. **Create function** → name: `sync-bms-alert`
3. Paste code from [`supabase/functions/sync-bms-alert/index.ts`](../supabase/functions/sync-bms-alert/index.ts)
4. Add secret: `BUILDOPT_WEBHOOK_SECRET` = `buildopt-alert-sync-2026-secret`
5. Deploy

Or with Supabase CLI (after `supabase login` and `supabase link`):

```bash
supabase secrets set BUILDOPT_WEBHOOK_SECRET=buildopt-alert-sync-2026-secret
supabase functions deploy sync-bms-alert
```

## 2. Railway backend variables

| Variable | Value |
|----------|--------|
| `SUPABASE_ALERT_WEBHOOK_URL` | `https://arddnpiluxrkndzzdpfi.supabase.co/functions/v1/sync-bms-alert` |
| `ALERT_WEBHOOK_SECRET` | `buildopt-alert-sync-2026-secret` |

## 3. Verify

```bash
curl -X POST https://buildopt-backend-production.up.railway.app/api/v1/health/alert-webhook/test
```

Expect `"status":"ok"` when `DEMO_MODE=false` and webhook is live.

Manual probe:

```bash
curl -X POST https://arddnpiluxrkndzzdpfi.supabase.co/functions/v1/sync-bms-alert \
  -H "Content-Type: application/json" \
  -H "x-buildopt-secret: buildopt-alert-sync-2026-secret" \
  -d '{"id":"manual-test-1","building_id":"burj-khalifa-01","severity":"info","category":"test","title":"Manual test","message":"Hello","acknowledged":true}'
```
