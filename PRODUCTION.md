# BuildOpt AI — Production Setup (Real Buildings)

This guide covers moving from **demo mode** (current state) to **live BMS data** for UAE/GCC sites.

**Current live stack:**
- Frontend: https://build-opt.site (Lovable)
- API: https://buildopt-backend-production.up.railway.app
- Supabase: `arddnpiluxrkndzzdpfi` (auth, alerts, work orders)

---

## Important: Cloud vs On-Prem

| Protocol | Where it runs | Why |
|----------|---------------|-----|
| **JCI Metasys REST** | Railway (cloud) | HTTP API — works if Metasys is reachable via VPN/public gateway |
| **InfluxDB** | InfluxDB Cloud | Time-series from any writer |
| **Supabase** | Supabase Cloud | Realtime alerts to frontend |
| **BACnet / Modbus / MQTT** | **Edge gateway on-site** | BMS lives on `192.168.x.x` — Railway cannot reach it directly |

```
┌─────────────────┐     HTTPS      ┌──────────────────┐
│  build-opt.site │ ─────────────► │ Railway API      │
└─────────────────┘                └────────┬─────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
            ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
            │ Metasys REST │        │ InfluxDB     │        │ Supabase     │
            │ (JCI v4)     │        │ Cloud        │        │ Realtime     │
            └──────────────┘        └──────────────┘        └──────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  BUILDING LAN (on-prem)                                                  │
│  ┌─────────┐   BACnet    ┌──────────────┐   HTTPS    ┌──────────────┐   │
│  │   BMS   │ ◄────────── │ Edge Gateway │ ─────────► │ Railway /    │   │
│  │ Metasys │   Modbus    │ (mini PC)    │            │ InfluxDB     │   │
│  └─────────┘   MQTT      └──────────────┘            └──────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Rollout phases

### Phase 0 — Today (demo + live API) ✅

You are here. Railway serves realistic demo data; frontend calls the real API.

```env
DEMO_MODE=true
APP_ENV=production
ALLOWED_ORIGINS=https://build-opt.site,https://www.build-opt.site
```

**Do not set `DEMO_MODE=false` yet** — most building endpoints still fall back to demo data until Phase 2–3 wiring is complete.

---

### Phase 1 — Metasys REST (first real integration)

**When:** You have Metasys v4 REST API access (VPN or on-site gateway).

**Railway variables:**

```env
JCI_METASYS_HOST=https://your-metasys-server.com
JCI_METASYS_USERNAME=buildopt_api
JCI_METASYS_PASSWORD=<strong-password>
JCI_METASYS_VERSION=v4
```

**Verify:**

```bash
curl https://buildopt-backend-production.up.railway.app/api/v1/jci/objects
curl https://buildopt-backend-production.up.railway.app/api/v1/health/protocols
```

**Metasys checklist (IT/BMS team):**
- [ ] API user with read (write only if setpoint write-back needed)
- [ ] JWT login at `POST /api/v4/login` works from Railway IP (may need firewall allowlist)
- [ ] Token auto-refresh (backend handles 14-min refresh)
- [ ] Document object IDs for chillers, AHUs, meters

**Network:** If Metasys is private IP only, deploy a **small reverse proxy or VPN** (Tailscale, Cloudflare Tunnel, site-to-site VPN) so Railway can reach the host URL.

---

### Phase 2 — InfluxDB + Supabase (persistence + realtime)

#### InfluxDB Cloud (free tier works for pilot)

1. Create bucket: `building_metrics`, org: `buildopt`
2. Generate API token with read/write on that bucket

**Railway:**

```env
INFLUX_URL=https://us-east-1-1.aws.cloud2.influxdata.com
INFLUX_TOKEN=<influx-api-token>
INFLUX_ORG=buildopt
INFLUX_BUCKET=building_metrics
```

**Data model (tags per point):**
- `building_id`, `device_id`, `point_name`
- Poll interval: 30 seconds (matches APScheduler design)

#### Supabase (your existing project)

**Railway** (server-side only — not Lovable `.env`):

```env
SUPABASE_URL=https://arddnpiluxrkndzzdpfi.supabase.co
SUPABASE_KEY=<anon-key>                    # optional for server
SUPABASE_SERVICE_KEY=<service-role-key>    # for alert inserts
```

**Supabase table** (if not exists — run in SQL editor):

```sql
create table if not exists public.building_alerts (
  id text primary key,
  building_id text not null,
  equipment_id text,
  severity text not null,
  category text,
  title text,
  message text,
  message_ar text,
  acknowledged boolean default false,
  created_at timestamptz default now()
);

alter table public.building_alerts enable row level security;

create policy "Authenticated read alerts"
  on public.building_alerts for select
  to authenticated using (true);
```

Frontend can subscribe via Supabase Realtime on `building_alerts`.

**PDPL:** Do not log personal data; anonymize user IDs in InfluxDB tags (already in `supabase_client.py`).

---

### Phase 3 — Edge gateway (BACnet / Modbus / MQTT)

Deploy **on the building network** (not Railway):

```bash
# On-site mini PC / NUC / Docker host
docker compose up -d   # full Dockerfile with BAC0 + pymodbus
```

**`.env` on edge:**

```env
DEMO_MODE=false
INFLUX_URL=<same InfluxDB Cloud URL>
INFLUX_TOKEN=<token>
RAILWAY_API_URL=https://buildopt-backend-production.up.railway.app
BACNET_IP=192.168.1.100
BACNET_PORT=47808
MODBUS_HOST=192.168.1.101
MQTT_BROKER=192.168.1.50
```

Edge polls BACnet/Modbus every 30s → writes InfluxDB → optional push to Railway.

**Requirements:**
- Same subnet as BMS (or BACnet router configured)
- Static IP for edge device
- Outbound HTTPS allowed (443) to InfluxDB + Railway

---

### Phase 4 — Flip `DEMO_MODE=false` (production cutover)

Only after:
- [ ] Live data flowing to InfluxDB for ≥ 24 hours
- [ ] Metasys or edge gateway validated
- [ ] Supabase alerts firing on FDD rules
- [ ] `/api/v1/health/protocols` shows `connected` / `ready` (not `simulated`)
- [ ] Frontend tested on build-opt.site with real numbers

**Railway:**

```env
DEMO_MODE=false
APP_ENV=production
SECRET_KEY=<long-random-string>
```

**Lovable `.env`** stays:

```env
VITE_API_URL=https://buildopt-backend-production.up.railway.app
VITE_DEMO_MODE=false
```

**Rollback:** Set `DEMO_MODE=true` on Railway — instant demo data restore.

---

## Railway production variables (full reference)

Copy into **Railway → Variables**:

```env
# Core
DEMO_MODE=true
APP_ENV=production
SECRET_KEY=<generate-32+-char-secret>
ALLOWED_ORIGINS=https://build-opt.site,https://www.build-opt.site,http://localhost:5173
TIMEZONE=Asia/Dubai
LATITUDE=25.2048
LONGITUDE=55.2708

# InfluxDB Cloud (Phase 2)
INFLUX_URL=
INFLUX_TOKEN=
INFLUX_ORG=buildopt
INFLUX_BUCKET=building_metrics

# Supabase (Phase 2)
SUPABASE_URL=https://arddnpiluxrkndzzdpfi.supabase.co
SUPABASE_KEY=
SUPABASE_SERVICE_KEY=

# JCI Metasys (Phase 1)
JCI_METASYS_HOST=
JCI_METASYS_USERNAME=
JCI_METASYS_PASSWORD=
JCI_METASYS_VERSION=v4

# BACnet/Modbus — edge gateway only (Phase 3), not Railway
# BACNET_IP=
# MODBUS_HOST=
```

---

## Per-building onboarding checklist

For each new site (e.g. HQ Tower, Dubai Media City):

1. **Discovery** — Export Metasys object list / BACnet point schedule
2. **Mapping** — Map points to `building_id`, equipment IDs in config
3. **Baseline** — 2 weeks of energy baseline for FDD rule #19 (15% deviation)
4. **DEWA** — Confirm commercial tariff tier; set in `dewa_tariff.py` if special
5. **GCC** — Set `LATITUDE` / `LONGITUDE` for prayer times (Aladhan method 8)
6. **Commissioning** — Compare API live data vs BMS screen for 24h
7. **Sign-off** — Facility manager validates setpoints before write-back enabled

---

## Verification commands

```bash
BASE=https://buildopt-backend-production.up.railway.app

# Core
curl $BASE/api/v1/health
curl $BASE/api/v1/health/protocols

# Live building
curl $BASE/api/v1/buildings/burj-khalifa-01/live

# JCI (after Phase 1)
curl $BASE/api/v1/jci/objects
curl $BASE/api/v1/jci/alarms

# GCC (real prayer times when DEMO_MODE=false + coords set)
curl $BASE/api/v1/gcc/prayer-times
```

---

## Security & compliance (UAE)

| Item | Action |
|------|--------|
| **PDPL** | No PII in logs; anonymize user IDs in metrics |
| **Secrets** | Railway Variables only — never in Lovable `.env` except public URLs |
| **Metasys write** | Separate API user; audit all `POST /jci/objects/{id}/command` |
| **CORS** | Keep `ALLOWED_ORIGINS` tight — only build-opt.site |
| **Arabic errors** | API returns `en` + `ar` in error payloads |

---

## Custom API domain (recommended before go-live)

Railway → **api.build-opt.site** → update Lovable:

```env
VITE_API_URL=https://api.build-opt.site
```

---

## What still uses demo data when `DEMO_MODE=false`

Today, several routes always call `demo_mode.py` (buildings list, energy, alerts, equipment). **Phase 4 code work** (future) will read from InfluxDB/Metasys instead. Until then:

- **`/api/v1/jci/*`** — real when Metasys creds set + `DEMO_MODE=false`
- **`/api/v1/health/protocols`** — real protocol status
- **`/api/v1/gcc/prayer-times`** — real Aladhan API when coords set
- **Buildings / energy / alerts** — still demo until InfluxDB + edge pipeline wired

Plan Metasys + InfluxDB first; then we extend API routes to read live series.

---

## Recommended next action (pick one)

| Priority | Task | Owner |
|----------|------|-------|
| **1** | Get Metasys REST URL + API credentials from JCI/site IT | Client IT |
| **2** | Create InfluxDB Cloud bucket + add tokens to Railway | You |
| **3** | Add `SUPABASE_SERVICE_KEY` to Railway; enable alerts table | You |
| **4** | Site survey for edge gateway (BACnet IP, subnet) | BMS integrator |
| **5** | VPN/tunnel so Railway reaches Metasys | Network team |

---

## Support contacts to prepare

- **JCI / Metasys** — API enablement, firewall rules
- **DEWA** — Commercial tariff account (peak/off-peak validation)
- **Building FM** — Setpoint approval, Ramadan schedules
- **Network** — Edge device, VLAN, outbound 443
