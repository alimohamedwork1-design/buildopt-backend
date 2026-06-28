# Paste into Lovable AI — wire ALL modules to Railway API

Railway API: `https://buildopt-backend-production.up.railway.app`  
Already in .env: `VITE_API_URL` and `VITE_DEMO_MODE=false`

Wire these pages to React Query hooks (create if missing in `src/hooks/useBuildOptApi.ts`):

| Page route | Hook | API |
|------------|------|-----|
| Overview `/` | useBuildingLive, useAlerts, useEnergyConsumption | /buildings/{id}/live, /alerts, /energy/consumption |
| Live Telemetry `/telemetry` | useBuildingLive | /buildings/{id}/live |
| Alert Intelligence `/alerts` | useAlerts, useFddResults | /alerts, /alerts/fdd |
| FDD Engine `/fdd` | useFddResults | /alerts/fdd |
| DEWA Hub `/dewa-hub` | useDewaTariff | /energy/dewa-tariff |
| Utility Rate Engine | useDewaTariff | /energy/dewa-tariff |
| Ramadan & Prayer `/ramadan-prayer` | usePrayerTimes, useRamadanMode | /gcc/prayer-times, /gcc/ramadan-mode |
| Sandstorm `/sandstorm` or GCC weather | useSandstormAlert | /gcc/sandstorm-alert |
| System Status | useApiHealth | /health |
| Portfolio / Executive | useBuildings | /buildings |

Rules:
- Pattern: `const apiOn = isApiEnabled(); const { data } = useX(); const value = apiOn && data ? map(data) : mockFallback`
- Keep mock-data.ts as fallback when API fails
- TopStatusBar: call useApiHealth(); show green "REST API: Live" when health.status === "healthy"
- Show BACnet/Modbus as separate status from /health/protocols when apiOn
- Do not remove Supabase auth

Implement all pages above in one pass.
