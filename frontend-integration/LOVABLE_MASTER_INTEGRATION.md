# BUILDOPT AI — MASTER LOVABLE INTEGRATION PROMPT
# Copy this ENTIRE file into Lovable AI chat. One pass. Republish after.

You are integrating build-opt.site with the production FastAPI backend at:
**https://buildopt-backend-production.up.railway.app**

.env is already set:
```
VITE_API_URL=https://buildopt-backend-production.up.railway.app
VITE_DEMO_MODE=false
```

---

## PHASE 1 — Add backend client files

Create these files exactly (copy from repo `frontend-integration/` or implement as described):

### `src/lib/buildopt-api.ts`
- Full API client with: site metadata, modules (all pages), sessions, buildings, energy, alerts, FDD, GCC, health
- `isApiEnabled()` = VITE_DEMO_MODE is "false" AND VITE_API_URL is set
- All requests to `${VITE_API_URL}/api/v1/...`

### `src/hooks/useBuildOptApi.ts`
- React Query hooks: `useModuleData`, `useBuildingLive`, `useAlerts`, `useFddResults`, `useDewaTariff`, `usePrayerTimes`, `useRamadanMode`, `useSandstormAlert`, `useApiHealth`, `useConnections`, `useEquipment`, `useEnergyConsumption`, `useEnergySavings`, `usePageViewTracking`, `trackLogin`, `trackLogout`

---

## PHASE 2 — Session tracking (login → backend)

### Modify `AuthProvider` (or create `src/components/BuildOptSessionSync.tsx`):

```tsx
import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { usePageViewTracking, trackLogin, trackLogout } from "@/hooks/useBuildOptApi";

export function BuildOptSessionSync({ children }: { children: React.ReactNode }) {
  const { user, roles } = useAuth();
  const role = roles?.[0];
  usePageViewTracking(user?.id, role);

  useEffect(() => {
    if (!user) return;
    trackLogin({ id: user.id, email: user.email }, role).catch(() => {});
  }, [user?.id]);

  return <>{children}</>;
}
```

Wrap `<AppLayout>` or protected routes with `<BuildOptSessionSync>`.

Also in demo auth (`/login` demo users): call `trackSessionEvent({ event_type: "login", email, role })` on successful demo login.

On signOut: call `trackLogout(user.id)`.

---

## PHASE 3 — Universal module data hook (ALL 172 pages)

Create `src/hooks/useModulePageData.ts`:

```tsx
import { useModuleData } from "@/hooks/useBuildOptApi";
import { useLocation } from "react-router-dom";

/** Use on ANY module page — auto-fetches backend data for current route */
export function useModulePageData() {
  const { pathname } = useLocation();
  const slug = pathname.replace(/^\//, "") || "overview";
  const { data, isLoading, error, refetch } = useModuleData(slug);
  return { data, isLoading, error, refetch, slug };
}
```

### Pattern for EVERY module page:

```tsx
import { isApiEnabled } from "@/lib/buildopt-api";
import { useModulePageData } from "@/hooks/useModulePageData";

export default function SomeModulePage() {
  const apiOn = isApiEnabled();
  const { data: apiData, isLoading } = useModulePageData();

  // Metric cards: prefer apiData.metric_cards, fallback to existing mock
  const metrics = apiOn && apiData?.metric_cards
    ? apiData.metric_cards
    : existingMockMetrics;

  // Recommendations: apiData.recommendations
  // Recent activity: apiData.recent_activity
  // Charts: apiData.charts
  // Live HVAC: apiData.live?.hvac
  // Alerts: apiData.alerts
  // FDD: apiData.fdd
  // Energy: apiData.energy
  // DEWA: apiData.dewa_tariff

  // Keep existing UI/layout — only replace data sources
}
```

Apply this pattern to **every lazy-loaded page component** in `src/pages/` or route chunks.

---

## PHASE 4 — Priority pages (wire first, then all others)

| Route | Primary API data |
|-------|------------------|
| `/` Overview | useBuildingLive + useAlerts + useModulePageData |
| `/telemetry` | useBuildingLive + useEnergyConsumption + useEquipment |
| `/alerts` | useAlerts (Railway primary; Supabase secondary when signed in) |
| `/fdd` | useFddResults + useModulePageData |
| `/dewa-hub` | useDewaTariff + useModulePageData |
| `/utility-rate` | useDewaTariff |
| `/ramadan-prayer` | usePrayerTimes + useRamadanMode |
| `/sandstorm-weather` | useSandstormAlert |
| `/equipment` | useEquipment + useModulePageData |
| `/work-orders` | Keep Supabase CRUD; add useModulePageData for metrics |
| `/data-health` | useConnections + useApiHealth |
| `/system-status` | useConnections + useProtocolStatus |
| `/settings` | useSiteMetadata |
| **All other 160+ routes** | useModulePageData() only |

---

## PHASE 5 — TopStatusBar & metadata

### TopStatusBar updates:
- `useApiHealth()` + `useConnections()` 
- REST API badge: green "Live" when `health.status === "healthy"`, red "Down" on error
- Show `connections.ingest_api`, `connections.alert_webhook` as tooltips
- Remove hardcoded "REST API: Live" — must reflect real health check

### `index.html` metadata (update):
```html
<meta name="description" content="BuildOpt AI — Intelligent BMS optimization for Dubai & GCC. Live HVAC, DEWA tariffs, FDD, Metasys integration." />
<meta property="og:title" content="BuildOpt AI — Smart Building Operations" />
<meta property="og:url" content="https://build-opt.site" />
<meta property="og:description" content="Real-time building intelligence — HQ Tower, Dubai Media City" />
<meta name="application-name" content="BuildOpt AI" />
<meta name="theme-color" content="#0a0f0a" />
```

### Fetch site metadata on app init (optional):
```tsx
// In App.tsx or main layout
const { data: siteMeta } = useSiteMetadata();
// Use siteMeta.building_name, siteMeta.version in footer/header
```

---

## PHASE 6 — Supabase edge function (alert sync)

Deploy `supabase/functions/sync-bms-alert/index.ts` from repo.

Add Lovable Cloud secret:
```
BUILDOPT_WEBHOOK_SECRET=buildopt-alert-sync-2026-secret
```

Railway already POSTs alerts to this webhook when FDD fires.

---

## PHASE 7 — Remove duplicate mock when API active

Create `src/lib/data-source.ts`:

```tsx
import { isApiEnabled } from "@/lib/buildopt-api";

export function pickApiOrMock<T>(apiValue: T | undefined, mockValue: T): T {
  return isApiEnabled() && apiValue !== undefined ? apiValue : mockValue;
}
```

Replace all inline mock fallbacks with `pickApiOrMock(apiData?.field, mockField)`.

Do NOT delete mock-data.ts — keep as offline fallback.

---

## PHASE 8 — ModuleFooter export

When `useModulePageData()` returns data, use `apiData` for CSV/PDF export rows instead of static mock arrays.

---

## RULES

1. **Never** put service_role or secrets in .env — only VITE_API_URL and VITE_DEMO_MODE
2. **Keep** Supabase auth — backend tracks login events, Supabase handles sessions
3. **Keep** all 172 routes and role-based access — do not remove modules
4. **Do not** break lazy loading in App.tsx
5. Every page must call `useModulePageData()` at minimum
6. Arabic error messages from API use `.message_ar` field on alerts
7. All timestamps display in Asia/Dubai (GST, UTC+4)
8. Show loading skeletons while `isLoading` from React Query
9. On API error, silently fall back to mock data (no user-facing crash)

---

## VERIFICATION CHECKLIST (after republish)

- [ ] Network tab shows calls to `buildopt-backend-production.up.railway.app/api/v1/...`
- [ ] Login triggers POST `/api/v1/sessions/events` with event_type login
- [ ] Every page navigation triggers page_view event
- [ ] Overview shows live HVAC kW from API (180-220 range)
- [ ] `/fdd` shows FDD results from `/api/v1/alerts/fdd`
- [ ] `/dewa-hub` shows DEWA tariff from API
- [ ] TopStatusBar REST badge reflects real health check
- [ ] GET `/api/v1/modules/telemetry/data` returns metric_cards + live data

Implement all phases now. Do not ask questions — use the patterns above for all pages.
