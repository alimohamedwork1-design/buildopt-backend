# Paste this entire block into Lovable AI chat

Connect this BuildOpt frontend to our FastAPI backend.

## Environment (already set in Lovable Secrets)
- VITE_API_URL = our deployed backend URL (calls go to `${VITE_API_URL}/api/v1/...`)
- VITE_DEMO_MODE = false

## Create these files

### 1. `src/lib/api-client.ts`
- Read `VITE_API_URL` and `VITE_DEMO_MODE` from import.meta.env
- Export `isApiEnabled()` → true only when VITE_DEMO_MODE is "false" AND VITE_API_URL is set
- Export fetch helpers for:
  - GET /buildings, /buildings/{id}/live, /energy/consumption, /energy/forecast, /energy/dewa-tariff, /energy/savings
  - GET /equipment, /alerts, /alerts/fdd
  - GET /gcc/prayer-times, /gcc/ramadan-mode, /gcc/sandstorm-alert
  - GET /health
- All requests: `fetch(\`${API_URL}/api/v1${path}\`)` with JSON headers
- Export TypeScript interfaces matching the API responses (LiveBuildingData with hvac, energy, environment)

### 2. `src/hooks/useBuildOptApi.ts`
- React Query hooks wrapping api-client: useBuildingLive, useAlerts, useEnergyConsumption, useDewaTariff, usePrayerTimes, useApiHealth
- Only enabled when isApiEnabled() is true
- useBuildingLive refetch every 5 seconds

## Wire pages (keep mock-data.ts as fallback when isApiEnabled() is false)

1. **Overview / dashboard** — use useBuildingLive("burj-khalifa-01") for HVAC kW, COP, temp, CO2; useAlerts() for alert count
2. **Live Telemetry** — useBuildingLive + useEnergyConsumption
3. **Alert Intelligence / FDD** — useAlerts() + useFddResults()
4. **Utility Rate Engine / DEWA** — useDewaTariff()
5. **Ramadan & Prayer Engine** — usePrayerTimes() + useRamadanMode()
6. **TopStatusBar** — useApiHealth(); when connected show green badge "REST API: Live" instead of "REST API: Awaiting"

## Rules
- Do NOT remove Supabase auth or existing mock-data.ts
- Pattern: `const apiOn = isApiEnabled(); const { data: live } = useBuildingLive(); const value = apiOn && live ? live.hvac.power_kw : mockValue`
- Handle loading states with existing UI skeletons
- Do not break any of the 178 modules — only wire the main telemetry modules listed above first

Implement now.
