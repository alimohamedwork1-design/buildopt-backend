# Connect build-opt.site (Lovable) to BuildOpt Backend

## 1. Deploy backend to Railway

See [DEPLOYMENT.md](../DEPLOYMENT.md) in the repo root.

After deploy you will have a URL like:

```
https://buildopt-backend-production.up.railway.app
```

Verify it works:

```
GET https://YOUR-URL/api/v1/health
GET https://YOUR-URL/api/v1/buildings/burj-khalifa-01/live
```

## 2. Add environment variables in Lovable

Open your Lovable project → **Settings → Environment Variables**:

| Variable | Value |
|----------|-------|
| `VITE_API_URL` | `https://YOUR-RAILWAY-URL` (no trailing slash) |
| `VITE_DEMO_MODE` | `false` |

Keep existing Supabase vars (`VITE_SUPABASE_URL`, etc.) — auth still uses Supabase.

## 3. Add API client files

Copy these files from `frontend-integration/` into your Lovable repo:

```
src/lib/api-client.ts          ← from frontend-integration/src/lib/api-client.ts
src/hooks/useBuildOptApi.ts    ← from frontend-integration/src/hooks/useBuildOptApi.ts
```

## 4. Wire the Overview page (example)

In your main dashboard / overview page, replace mock-only data with API when enabled:

```tsx
import { isApiEnabled } from "@/lib/api-client";
import { useBuildingLive, useAlerts, useEnergyConsumption } from "@/hooks/useBuildOptApi";
import { mockEnergyToday } from "@/lib/mock-data"; // keep as fallback

export default function Overview() {
  const apiOn = isApiEnabled();
  const { data: live } = useBuildingLive("burj-khalifa-01");
  const { data: alerts } = useAlerts();
  const { data: energy } = useEnergyConsumption();

  const energyToday = apiOn && energy
    ? Math.round(energy.total_kw * 24 * 0.12) // example mapping
    : mockEnergyToday;

  const activeAlerts = apiOn && alerts ? alerts.length : 2;

  // Use live?.hvac.power_kw, live?.environment.temp_c, etc.
}
```

## 5. Lovable AI prompt (paste into chat)

```
Connect the BuildOpt frontend to the FastAPI backend:

1. Add src/lib/api-client.ts and src/hooks/useBuildOptApi.ts (already provided)
2. Set VITE_API_URL and VITE_DEMO_MODE=false in env
3. On the Overview page and Live Telemetry page, use useBuildingLive() when isApiEnabled() is true, otherwise keep mock-data.ts
4. On Alerts page, use useAlerts() and useFddResults()
5. On DEWA / Utility Rate pages, use useDewaTariff()
6. On Ramadan & Prayer Engine page, use usePrayerTimes() and useRamadanMode()
7. Show a small "REST API: Live" badge in TopStatusBar when getHealth() returns demo_mode=false
8. Do NOT remove Supabase auth — only replace building telemetry mock data with API calls
```

## 6. CORS checklist

Railway env var `ALLOWED_ORIGINS` must include:

```
https://build-opt.site,https://www.build-opt.site,http://localhost:5173
```

If Lovable gives you a preview URL (e.g. `*.lovable.app`), add that too.

## 7. Rollback

Set `VITE_DEMO_MODE=true` in Lovable — frontend instantly falls back to local mock data with no backend calls.
