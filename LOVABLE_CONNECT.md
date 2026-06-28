# Connect BuildOpt Backend ↔ Lovable (build-opt.site)

You need **two things**: a public backend URL + two env vars in Lovable.

---

## Step 1 — Get a backend URL

Pick **one**:

### Option A — Railway (recommended for build-opt.site)

1. Push this repo to GitHub and deploy on [railway.app](https://railway.app) (see `DEPLOYMENT.md`)
2. Generate a public domain, e.g. `https://buildopt-backend-production.up.railway.app`
3. Test in browser: `https://YOUR-URL/api/v1/health`

### Option B — Test locally with a tunnel (quick try)

```powershell
cd "C:\Users\Ali Mohamed\Projects\buildopt-backend"
.\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In another terminal, run [ngrok](https://ngrok.com) or Cloudflare Tunnel:

```powershell
ngrok http 8000
```

Use the `https://xxxx.ngrok-free.app` URL as your API URL (temporary only).

---

## Step 2 — Set Lovable environment variables

1. Open your **BuildOpt project in Lovable** (the one that publishes to build-opt.site)
2. Go to **Project → Settings → Environment Variables** (or **Secrets**)
3. Add:

| Name | Value |
|------|-------|
| `VITE_API_URL` | `https://YOUR-BACKEND-URL` (no trailing `/`) |
| `VITE_DEMO_MODE` | `false` |

Keep your existing Supabase vars (`VITE_SUPABASE_URL`, etc.) — login still uses Supabase.

4. **Redeploy / republish** the Lovable app after saving env vars (Vite bakes `VITE_*` at build time).

---

## Step 3 — Paste this into Lovable AI chat

Open **Lovable chat** in your BuildOpt project and paste the full prompt from:

**`frontend-integration/LOVABLE_AI_PROMPT.md`**

That prompt tells Lovable to:
- Create `src/lib/api-client.ts`
- Create `src/hooks/useBuildOptApi.ts`
- Wire Overview, Live Telemetry, Alerts, DEWA, and GCC pages to the API
- Show **REST API: Live** in the status bar when connected

---

## Step 4 — Verify in the browser

1. Open build-opt.site (or Lovable preview)
2. Open DevTools → **Network** tab
3. You should see requests to `YOUR-BACKEND-URL/api/v1/...`
4. Overview should show live HVAC/energy numbers from the backend

If you see **CORS errors**, add your exact site URL to Railway:

```
ALLOWED_ORIGINS=https://build-opt.site,https://www.build-opt.site,http://localhost:5173
```

(Lovable preview `*.lovable.app` is already allowed by the backend.)

---

## Rollback

In Lovable, set `VITE_DEMO_MODE=true` and redeploy — the app uses local mock data again.

---

## Files already in this repo (for reference)

```
frontend-integration/src/lib/api-client.ts
frontend-integration/src/hooks/useBuildOptApi.ts
frontend-integration/LOVABLE_SETUP.md
```
