# BUILDOPT AI — MASTER LOVABLE INTEGRATION PROMPT V2
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

### Fetch site metadata on app init:
```tsx
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

## PHASE 9 — BMS Connection Settings Page ⭐ NEW

Create a new page at route `/bms-settings` and add it to the sidebar under "Settings".

### UI Design:
- Background: `#070B14`, accent: `#00C8FF`, border-radius: max 4px
- IBM Plex Mono for values, IBM Plex Sans for labels
- Page title: "BMS & Protocol Connections"
- Subtitle: "Connect your building management systems to BuildOpt AI"

### Section 1 — Johnson Controls Metasys Card:
```tsx
// Card with JCI logo placeholder + green/red status badge
// Fields:
<input placeholder="https://metasys.building.com" />   // Metasys Server URL
<input placeholder="buildopt_api" />                    // API Username
<input type="password" placeholder="••••••••" />        // API Password
<select defaultValue="v4">                              // API Version
  <option value="v4">Metasys v4 (Recommended)</option>
  <option value="v3">Metasys v3</option>
</select>

// Buttons:
<button onClick={testConnection}>Test Connection</button>   // cyan outline
<button onClick={saveCredentials}>Save & Connect</button>   // cyan filled

// Status display:
// ⚪ Disconnected | 🔄 Testing... | ✅ Connected | ❌ Failed: [error message]
```

### On "Test Connection" click:
```tsx
const res = await fetch(`${VITE_API_URL}/api/v1/jci/test-connection`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ host, username, password, version })
});
const data = await res.json();
// data.status === "connected" → show ✅ Connected (response_ms ms)
// data.status === "failed"    → show ❌ Failed: data.error
```

### On "Save & Connect" click:
```tsx
const res = await fetch(`${VITE_API_URL}/api/v1/jci/save-credentials`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ host, username, password, version })
});
// On success: green toast "Metasys Connected Successfully — Live data active"
// On fail: red toast with error
```

### Section 2 — Future Protocols (grayed out / coming soon badge):
```
🔲 BACnet/IP        [Coming Soon — Requires Edge Gateway]
🔲 Modbus TCP       [Coming Soon — Requires Edge Gateway]
🔲 MQTT Broker      [Coming Soon — Requires Edge Gateway]
🔲 OPC-UA           [Coming Soon]
```

Each card shows: protocol name, icon, description, "Edge Gateway Required" badge in orange.

### Section 3 — Connection Status Summary:
Live table auto-refreshing every 30s:
```
Protocol      | Status        | Last Seen        | Data Points
Metasys REST  | ✅ Connected  | 2 seconds ago    | 847
InfluxDB      | ✅ Connected  | 5 seconds ago    | 12,450 records
Supabase      | ✅ Connected  | realtime         | alerts: 3
BACnet        | ⚪ Not configured | —             | —
Modbus        | ⚪ Not configured | —             | —
```

Fetch from: `GET /api/v1/health/protocols`

### Section 4 — Network Diagnostic Tool:
Button: "Run Network Check"
```tsx
// On click: POST /api/v1/jci/test-connection with current saved credentials
// Shows ping latency, SSL cert validity, API version confirmed
// Results:
// ✅ DNS resolved in 45ms
// ✅ TCP port 443 open
// ✅ SSL certificate valid (expires: 2025-12-01)
// ✅ Metasys API v4 responded in 312ms
// ✅ JWT login successful
// ⚠️  Token refresh: 14 min interval set
```

---

## PHASE 10 — System Health Dashboard ⭐ NEW

Create or upgrade `/system-status` page with full continuous monitoring:

### Auto-refresh every 30 seconds (useInterval):
```tsx
const { data: health } = useQuery({
  queryKey: ["system-health"],
  queryFn: () => fetch(`${API}/api/v1/health`).then(r => r.json()),
  refetchInterval: 30_000,
  refetchIntervalInBackground: true,
});
```

### Sections:

**1) Overall Health Score (0-100):**
```
Large number display: e.g. "98" in cyan
Label: "System Health Score"
Subtext: "All systems operational" / "1 warning detected" / "Action required"
```

**2) Services Grid (real-time badges):**
```
Railway API     ✅ 99.9% uptime    Response: 145ms
InfluxDB        ✅ Connected       Write rate: 120 pts/min
Supabase        ✅ Realtime active Latency: 23ms
Metasys REST    ✅ Connected       Last poll: 28s ago
BACnet          ⚪ Not configured
Modbus          ⚪ Not configured
```

**3) API Response Time Chart (last 24h):**
Line chart — x: time, y: response_ms
Data from: `GET /api/v1/health/history`
Colors: cyan line on dark background

**4) Error Log (last 10 errors):**
```
[14:23:01] WARNING  Metasys token refreshed (was 13m 58s old)
[13:45:22] INFO     InfluxDB write batch: 240 points
[12:30:11] ERROR    BACnet: device 192.168.1.100 unreachable (not configured)
```
Fetch from: `GET /api/v1/health/logs?limit=10`

**5) Data Pipeline Status:**
```
Sensor Poll     → Every 30s    ✅ Last run: 12s ago
FDD Engine      → Every 60s    ✅ Last run: 45s ago
ML Anomaly      → Every 5min   ✅ Last run: 2m ago
DEWA Tariff     → Every 1h     ✅ Last run: 23m ago
Prayer Times    → Every 24h    ✅ Last run: 6h ago
```
Fetch from: `GET /api/v1/health/pipeline`

**6) Alert if any service is down:**
If `health.status !== "healthy"` → show red banner at top of ALL pages:
```tsx
// In AppLayout — check health every 60s
// If down: <div className="bg-red-900 text-white p-2 text-center">
//   ⚠️ API connection issue — showing cached data
// </div>
```

---

## PHASE 11 — Global Connection Monitor ⭐ NEW

Create `src/components/ConnectionMonitor.tsx`:

```tsx
// Runs silently in background on ALL pages
// Checks /api/v1/health every 60 seconds
// If 2 consecutive failures → show toast: "⚠️ Backend connection lost — using cached data"
// If recovers → show toast: "✅ Backend reconnected"
// Logs all status changes to browser console with timestamps

export function ConnectionMonitor() {
  const [failures, setFailures] = useState(0);
  
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/health`, { timeout: 5000 });
        if (!res.ok) throw new Error();
        setFailures(0);
        // if was down: show reconnect toast
      } catch {
        setFailures(f => f + 1);
        if (failures >= 1) {
          // show "connection lost" toast
        }
      }
    };
    
    const interval = setInterval(check, 60_000);
    check(); // run immediately
    return () => clearInterval(interval);
  }, [failures]);
  
  return null; // invisible component
}
```

Add `<ConnectionMonitor />` inside `<AppLayout>` so it runs on every page.

---

## PHASE 12 — Data Freshness Indicators ⭐ NEW

On every page that shows live data, add a small indicator showing when data was last updated:

```tsx
// Component: <DataFreshness timestamp={apiData?.fetched_at} />
// Shows: "Updated 5s ago" in gray text, bottom right of each data card
// Green dot if < 60s ago
// Yellow dot if 60s–5min ago  
// Red dot if > 5min ago (stale)
// Clicking it triggers manual refetch
```

Create `src/components/DataFreshness.tsx` and use on:
- Overview page (all metric cards)
- Telemetry page
- Equipment page
- Alerts page
- FDD page

---

## PHASE 13 — One-Click Demo vs Live Toggle ⭐ NEW

Add a toggle in the TopStatusBar or Settings:

```tsx
// "Demo Mode" switch — visible only to admin role
// When ON: VITE_DEMO_MODE=true behavior (simulated data)
// When OFF: live API data
// Stores preference in localStorage: "buildopt_demo_mode"
// Shows label: "DEMO" badge in yellow when demo mode active
// Useful for showing JCI demo without real building connected
```

```tsx
// In buildopt-api.ts — override isApiEnabled():
export function isApiEnabled(): boolean {
  const localOverride = localStorage.getItem("buildopt_demo_mode");
  if (localOverride === "true") return false;  // force demo
  if (localOverride === "false") return true;  // force live
  return import.meta.env.VITE_DEMO_MODE !== "true" 
    && !!import.meta.env.VITE_API_URL;
}
```

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
10. `/bms-settings` visible to admin role only
11. ConnectionMonitor runs on ALL pages silently
12. DataFreshness component on all live-data pages
13. Demo/Live toggle visible to admin role only

---

## VERIFICATION CHECKLIST (after republish)

### Original checks:
- [ ] Network tab shows calls to `buildopt-backend-production.up.railway.app/api/v1/...`
- [ ] Login triggers POST `/api/v1/sessions/events` with event_type login
- [ ] Every page navigation triggers page_view event
- [ ] Overview shows live HVAC kW from API (180-220 range)
- [ ] `/fdd` shows FDD results from `/api/v1/alerts/fdd`
- [ ] `/dewa-hub` shows DEWA tariff from API
- [ ] TopStatusBar REST badge reflects real health check
- [ ] GET `/api/v1/modules/telemetry/data` returns metric_cards + live data

### New checks (V2):
- [ ] `/bms-settings` page loads with Metasys connection form
- [ ] "Test Connection" button calls `/api/v1/jci/test-connection` and shows result
- [ ] "Save & Connect" button saves credentials and shows success toast
- [ ] Protocol status table on `/bms-settings` auto-refreshes every 30s
- [ ] `/system-status` shows real-time health score + services grid
- [ ] API response time chart visible on `/system-status`
- [ ] ConnectionMonitor shows toast when backend is unreachable
- [ ] ConnectionMonitor shows recovery toast when backend comes back
- [ ] DataFreshness indicator visible on Overview, Telemetry, Equipment pages
- [ ] Green dot when data < 60s old, yellow 1-5min, red > 5min
- [ ] Demo/Live toggle visible in TopStatusBar for admin role
- [ ] "DEMO" yellow badge shows when demo mode is active
- [ ] Red banner appears on ALL pages when API is down
- [ ] Network Diagnostic Tool on `/bms-settings` runs full check
- [ ] Future protocol cards (BACnet, Modbus, MQTT) show "Coming Soon" badge

Implement all phases now. Do not ask questions — use the patterns above for all pages.
