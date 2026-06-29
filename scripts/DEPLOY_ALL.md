# Deploy both BuildOpt services to Railway

Run from PowerShell after `railway login` and linking each service.

## Backend

```powershell
cd C:\Users\Ali Mohamed\Projects\buildopt-backend
railway up --service buildopt-backend
```

## Frontend

```powershell
cd C:\Users\Ali Mohamed\Projects\buildopt-ai
railway up --service buildopt-frontend
```

## Post-deploy verification

```powershell
cd C:\Users\Ali Mohamed\Projects\buildopt-backend
.\scripts\verify-production.ps1
```

## Go-live checklist

1. Metasys credentials at https://build-opt.site/settings?tab=bms
2. Map object IDs: `PUT /api/v1/jci/buildings/burj-khalifa-01/objects`
3. Apply Supabase migration `20260629030000_default_user_role.sql`
4. Set `DEMO_MODE=false` on Railway when Influx + Metasys are ready
5. Enable Google OAuth provider in Supabase dashboard
