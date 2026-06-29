# Paste into Lovable AI chat — deploy Supabase alert sync edge function

Deploy the BMS alert webhook so Railway can push FDD alerts into Supabase **without** exposing `service_role` in the frontend or Railway env.

---

## 1. Create edge function

Create **`supabase/functions/sync-bms-alert/index.ts`** with this exact code:

```typescript
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-buildopt-secret",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  const secret = Deno.env.get("BUILDOPT_WEBHOOK_SECRET");
  if (secret && req.headers.get("x-buildopt-secret") !== secret) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  try {
    const alert = await req.json();
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const row = {
      id: alert.id,
      building_id: alert.building_id,
      equipment_id: alert.equipment_id ?? null,
      severity: alert.severity,
      category: alert.category,
      title: alert.title,
      message: alert.message,
      message_ar: alert.message_ar ?? alert.message,
      acknowledged: alert.acknowledged ?? false,
      created_at: alert.timestamp ?? new Date().toISOString(),
    };

    for (const table of ["building_alerts", "alerts"]) {
      const { error } = await supabase.from(table).upsert(row);
      if (!error) {
        return new Response(JSON.stringify({ success: true, table }), {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
    }

    throw new Error("Could not upsert alert to building_alerts or alerts");
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
```

---

## 2. Add Lovable Cloud secret

In **Lovable Cloud → Secrets** (NOT `.env`):

```
BUILDOPT_WEBHOOK_SECRET=buildopt-alert-sync-2026-secret
```

`SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_URL` are auto-injected for edge functions — do not copy them to `.env`.

---

## 3. Deploy the function

Deploy `sync-bms-alert` via Lovable Supabase integration.

Expected URL:
```
https://arddnpiluxrkndzzdpfi.supabase.co/functions/v1/sync-bms-alert
```

---

## 4. Tell backend operator to set Railway vars

After deploy, set on Railway (`buildopt-backend`):

```
SUPABASE_ALERT_WEBHOOK_URL=https://arddnpiluxrkndzzdpfi.supabase.co/functions/v1/sync-bms-alert
ALERT_WEBHOOK_SECRET=buildopt-alert-sync-2026-secret
```

---

## 5. Verify

```bash
curl -X POST https://buildopt-backend-production.up.railway.app/api/v1/health/alert-webhook/test
```

When `DEMO_MODE=false` on Railway, expect `"status":"ok"`.

Manual probe (optional):

```bash
curl -X POST https://arddnpiluxrkndzzdpfi.supabase.co/functions/v1/sync-bms-alert \
  -H "Content-Type: application/json" \
  -H "x-buildopt-secret: buildopt-alert-sync-2026-secret" \
  -d '{"id":"manual-test-1","building_id":"burj-khalifa-01","severity":"info","category":"test","title":"Manual test","message":"Hello","acknowledged":true}'
```

Do NOT add `service_role` to frontend `.env`. Edge function only.
