# BuildOpt — Full Site Integration

## Site audit (build-opt.site)

- **177 routes** (172 modules + auth)
- **6 routes** previously wired to Railway API
- **165+ routes** were mock-only → now served via `/api/v1/modules/{slug}/data`

## Backend (deployed)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/site/metadata` | Site name, version, building, features |
| `GET /api/v1/modules` | All 172 module registry |
| `GET /api/v1/modules/{slug}/data` | **Universal data for any page** |
| `POST /api/v1/sessions/events` | Login, page_view, logout tracking |
| `GET /api/v1/sessions/stats` | Active user stats |
| Existing `/buildings`, `/energy`, `/alerts`, `/gcc`, etc. | Specialized endpoints |

## Lovable — ONE prompt to configure everything

Paste into Lovable chat:

### **`frontend-integration/LOVABLE_MASTER_INTEGRATION.md`**

This configures:
- All 172 pages → `useModulePageData()` hook
- Login → backend session tracking (PDPL-safe, anonymized)
- Page views → automatic backend events
- TopStatusBar → real health check
- Metadata → index.html SEO tags
- Priority pages → specialized hooks (live, FDD, DEWA, prayer)
- Supabase edge function for alert sync

### Files to copy into Lovable repo

```
src/lib/buildopt-api.ts          ← frontend-integration/src/lib/buildopt-api.ts
src/hooks/useBuildOptApi.ts      ← frontend-integration/src/hooks/useBuildOptApi.ts
```

## Verify after Lovable republish

```bash
# Any module page
curl https://buildopt-backend-production.up.railway.app/api/v1/modules/fdd/data

# Login tracking
curl -X POST https://buildopt-backend-production.up.railway.app/api/v1/sessions/events \
  -H "Content-Type: application/json" \
  -d '{"event_type":"login","email":"demo@buildopt.ai","role":"facility_manager"}'

# Site metadata
curl https://buildopt-backend-production.up.railway.app/api/v1/site/metadata
```

On build-opt.site: F12 → Network → filter `railway` → every page should hit `/modules/{slug}/data`
