# Metasys Integration (JCI REST)

**Last updated:** 2026-08-29  
**Client:** `buildopt-backend/app/services/jci_metasys.py`  
**API routes:** `buildopt-backend/app/api/jci.py`

## Status summary

| Area | Status | Notes |
|------|--------|-------|
| Login + JWT refresh | COMPLETE | 14-minute token cache, `POST /api/{version}/login` |
| Object discovery | COMPLETE | `get_objects()`, tree flatten in `metasys_auto_mapper.py` |
| Present value read | COMPLETE | Per-object attribute read |
| Alarms + trends | PARTIAL | Implemented; not validated on live site |
| Write command | PARTIAL | `write_command()` exists; gated by `write_policy.py` |
| Demo path | COMPLETE | Returns `demo_mode.get_jci_objects()` when `DEMO_MODE=true` |
| Production E2E | **NOT PROVEN** | Blocker B1 — needs pilot credentials + tunnel |

## Metasys REST endpoints used

| BuildOpt API | Upstream Metasys | Method | Auth |
|--------------|------------------|--------|------|
| `POST /api/v1/jci/test-connection` | `/api/v4/login` + object count | POST + GET | Bearer after login |
| `GET /api/v1/jci/objects` | `/api/v4/objects` | GET | Bearer |
| `GET /api/v1/jci/objects/{id}/present-value` | `/api/v4/objects/{id}/attributes/presentValue` | GET | Bearer |
| `POST /api/v1/jci/objects/{id}/command` | `/api/v4/objects/{id}/commands` | POST | Bearer |
| `GET /api/v1/jci/alarms` | `/api/v4/alarms` (client method) | GET | Bearer |
| `GET /api/v1/jci/trends/{object_id}` | Trend API (client method) | GET | Bearer |

Version defaults to `v4` (`JCI_METASYS_VERSION`).

## BuildOpt API routes

| Route | Purpose |
|-------|---------|
| `POST /api/v1/jci/test-connection` | Live probe (never uses demo token) |
| `POST /api/v1/jci/save-credentials` | Persist + optional live test + auto-connect |
| `POST /api/v1/jci/network-diagnostic` | DNS/TLS/socket diagnostics |
| `GET /api/v1/jci/logical-keys` | Canonical keys (`hvac` or `refrigeration` domain) |
| `POST /api/v1/jci/auto-connect` | Discover → map → poll all buildings |
| `POST /api/v1/jci/buildings/{id}/objects/auto-map` | Per-building fuzzy mapping |
| `GET/PUT /api/v1/jci/buildings/{id}/objects` | Read/update object map |
| `GET /api/v1/jci/object-mappings` | All building maps |

## Configuration

### Railway env (`railway.env.template`)

```
JCI_METASYS_HOST=
JCI_METASYS_USERNAME=
JCI_METASYS_PASSWORD=
JCI_METASYS_VERSION=v4
```

### Supabase

Encrypted credentials in `building_connections` (migration `002_bms_connections.sql`). Loaded at startup via `connection_store.load_metasys_from_supabase()` in `app/main.py`.

### Frontend

- Settings UI: `buildopt-ai/src/pages/BmsSettings.tsx`
- JCI service (if present): `buildopt-ai/src/services/jciAPI.ts`

## Network requirements

1. Metasys REST API enabled (JCI v4+).
2. API user with **read** scope (write only if write-back approved).
3. `JCI_METASYS_HOST` must be HTTPS reachable from Railway (public URL or **Cloudflare Tunnel** / VPN — see `PRODUCTION.md`).
4. Firewall allowlist for Railway egress IPs.

## Test requirements

### Automated (CI / local)

| Test file | Coverage |
|-----------|----------|
| `tests/test_metasys_auto_mapper.py` | Flatten, fuzzy `suggest_mappings` |
| `tests/test_protocols.py` | Protocol status shapes |
| `tests/test_live_data_production.py` | No silent demo when Metasys absent |

Run:

```powershell
cd buildopt-backend
pytest tests/test_metasys_auto_mapper.py tests/test_protocols.py -q
```

### Manual — connection test

```bash
curl -X POST https://buildopt-backend-production.up.railway.app/api/v1/jci/test-connection \
  -H "Content-Type: application/json" \
  -d '{"host":"https://metasys.example.com","username":"buildopt_api","password":"***","version":"v4"}'
```

**Pass criteria:** `status: "connected"`, `object_count > 0`, `response_ms < 5000`.

### Manual — save + auto-map

1. Save credentials via UI or `POST /api/v1/jci/save-credentials`.
2. `POST /api/v1/jci/buildings/{building_id}/objects/auto-map?merge=true`.
3. **Pass:** `mapped_keys >= 4` for typical HVAC site.
4. `GET /api/v1/health/protocols` → `metasys.status = connected`.

### Manual — live telemetry

1. Set `DEMO_MODE=false` on Railway (pilot only).
2. Wait one poll cycle (`POLL_INTERVAL_SECONDS=30`).
3. `GET /api/v1/buildings/{id}/live` returns non-null readings with `demo_mode: false`.
4. InfluxDB bucket `building_metrics` receives writes.

### Manual — write-back (disabled by default)

`POST /api/v1/jci/objects/{id}/command` must return **403** `COMMAND_NOT_ALLOWED` until `WriteMode` is elevated (see `docs/writeback-safety.md`).

## Known gaps

- No automated integration test against real Metasys (credentials in CI secrets TBD).
- SSRF risk: user-supplied `host` in test-connection — validate in Phase 2 security hardening.
- Demo building IDs differ between `demo_mode.py` and `buildings_registry.py` — align before pilot.

## Related

- `docs/point-mapping.md` — logical keys
- `docs/integration-architecture.md` — tunnel + edge
- `PRODUCTION.md` § Phase 1
