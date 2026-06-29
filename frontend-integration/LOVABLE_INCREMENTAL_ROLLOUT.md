# Paste into Lovable AI chat — incremental API rollout (172 pages)

Wire build-opt.site to Railway **without breaking mocks**. Adopt pages in batches; each page keeps mock fallback when API is off or loading.

.env (already set):
```
VITE_API_URL=https://buildopt-backend-production.up.railway.app
VITE_DEMO_MODE=false
```

---

## Batch 0 — Copy files (once)

Copy from repo `frontend-integration/` into the Lovable project:

| Source | Destination |
|--------|-------------|
| `src/lib/buildopt-api.ts` | `src/lib/buildopt-api.ts` |
| `src/lib/data-source.ts` | `src/lib/data-source.ts` |
| `src/hooks/useBuildOptApi.ts` | `src/hooks/useBuildOptApi.ts` |
| `src/hooks/useModulePageData.ts` | `src/hooks/useModulePageData.ts` |
| `src/components/BuildOptSessionSync.tsx` | `src/components/BuildOptSessionSync.tsx` |

Wrap protected layout with `<BuildOptSessionSync>` (login + page_view tracking).

---

## Batch 1 — Priority pages (wire first)

Use specialized hooks **plus** `useModulePageData()`:

| Route | Hooks |
|-------|-------|
| `/` | `useBuildingLive`, `useAlerts`, `useModulePageData` |
| `/telemetry` | `useBuildingLive`, `useEnergyConsumption`, `useEquipment` |
| `/alerts` | `useAlerts` |
| `/fdd` | `useFddResults`, `useModulePageData` |
| `/dewa-hub`, `/utility-rate` | `useDewaTariff`, `useModulePageData` |
| `/data-health` | `useApiHealth`, `useProtocolHealth`, `useHealthHistory`, `useHealthLogs`, `useHealthPipeline` |
| `/system-status` | `useConnections`, `useProtocolHealth`, `useHealthPipeline` |
| `/settings` | `useSiteMetadata` |

### Page pattern (every module)

```tsx
import { pickApiOrMock, pickApiArray } from "@/lib/data-source";
import { isApiEnabled } from "@/lib/buildopt-api";
import { useModulePageData } from "@/hooks/useModulePageData";

export default function ExamplePage() {
  const apiOn = isApiEnabled();
  const { data: apiData, isLoading } = useModulePageData();

  const metrics = pickApiOrMock(apiData?.metric_cards, existingMockMetrics);
  const recommendations = pickApiArray(apiData?.recommendations, mockRecommendations);

  if (apiOn && isLoading) {
    return <PageSkeleton />; // keep existing skeleton if available
  }

  // existing JSX — only data sources change
}
```

---

## Batch 2 — Remaining pages (incremental)

For **each** lazy-loaded page in `src/pages/` (or route modules):

1. Add `const { data: apiData, isLoading } = useModulePageData();`
2. Replace metric/card/chart arrays with `pickApiOrMock` / `pickApiArray`
3. Do **not** delete `mock-data.ts`
4. Do **not** remove Supabase auth or role guards

Process ~20–30 pages per Lovable pass to avoid timeout. Repeat until all 172 module routes call `useModulePageData()` at minimum.

---

## Batch 3 — TopStatusBar + exports

- TopStatusBar: `useApiHealth()` — badge green when `health.status === "healthy"`, show `health_score` if present
- ModuleFooter CSV/PDF: use `apiData` rows when `isApiEnabled()`

---

## Rules

1. Never put secrets in `.env` — only `VITE_API_URL` and `VITE_DEMO_MODE`
2. On API error → silent fallback to mock (no crash)
3. Keep all routes and lazy loading
4. Arabic: use `message_ar` on alerts when locale is Arabic

---

## Verify after each batch

F12 → Network → filter `railway`:

- Every navigated page should hit `/api/v1/modules/{slug}/data`
- Login → POST `/api/v1/sessions/events` with `event_type: login`
- `/data-health` → `/health/protocols`, `/health/history`, `/health/logs`, `/health/pipeline`

Implement Batch 0 + Batch 1 now. List remaining page files for Batch 2.
