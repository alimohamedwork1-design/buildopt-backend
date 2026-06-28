# Paste into Lovable AI chat — deploy Supabase alert sync (no dashboard access needed)

Deploy the edge function at `supabase/functions/sync-bms-alert/index.ts` (copy from this repo's `frontend-integration/supabase/functions/sync-bms-alert/`).

1. Create `supabase/functions/sync-bms-alert/index.ts` with the provided code
2. In Supabase/Lovable Cloud secrets, ensure `SUPABASE_SERVICE_ROLE_KEY` exists (Lovable auto-provides for edge functions)
3. Add secret `BUILDOPT_WEBHOOK_SECRET` = `buildopt-alert-sync-2026-secret` in Lovable Cloud secrets
4. Deploy the edge function

The Railway backend will POST alerts to:
`https://arddnpiluxrkndzzdpfi.supabase.co/functions/v1/sync-bms-alert`

Do NOT add service_role to .env or frontend. Edge function only.
