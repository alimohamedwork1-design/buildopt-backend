# Phase 4 Report — Semantic Mapping V2 & Scoped Gateway Security

**Date:** 2026-08-29  
**Status:** PASS (implementation + verification)

---

## 1. Semantic Mapping Architecture

### Lifecycle

```text
Metasys Discovery → Raw Point Registry → Semantic Suggestions → Human Review → Approval → Collection Config → Edge Collection
```

| Stage | API / Module | Notes |
|-------|--------------|-------|
| Registry | `POST /discovery/points/batch` | Immutable `source_point_id`; suggestions never mutate identity |
| Suggestions | `GET /semantic/buildings/{id}/suggestions` | Confidence from `semantic_mapper.py` (≥0.95 auto-candidate, ≥0.75 review) |
| Approval | `POST /semantic/buildings/{id}/approve` | Explicit write; rejects confidence < 0.75 when confidence supplied |
| Collection config | `GET /semantic/buildings/{id}/collection-config` | Approved mappings only |
| Edge fetch | `GET /gateways/{gateway_id}/collection-config` | Gateway token or master key |

### Guarantees

- Suggestions are read-only against registry rows
- Low-confidence mappings are never silently approved
- Collection config excludes unapproved / rejected mappings
- Approvals are building-scoped (`building_mismatch` rejected)
- `source_point_id` remains traceable in config export

---

## 2. Gateway Token Security Model

| Property | Implementation |
|----------|----------------|
| Randomness | `secrets.token_urlsafe(24)` |
| Plaintext storage | Never — SHA-256 hash with `SECRET_KEY` pepper |
| Plaintext return | Once at `POST /gateways/{id}/tokens` only |
| List tokens | Metadata only (`token_id`, label, timestamps) |
| Revocation | Immediate via `DELETE /gateways/{id}/tokens/{token_id}` |
| Scope | Token prefix `bo_gw_{gateway_id}_`; validated against request `gateway_id` |
| Admin endpoints | `verify_master_ingest_key` — gateway tokens rejected |
| Edge credential | `GATEWAY_API_KEY` env (preferred over shared `INGEST_API_KEY`) |

Migration **008** (`gateway_tokens`) applied to Lovable Cloud Postgres.

---

## 3. Influx History Architecture

- Endpoint: `GET /api/v1/buildings/{id}/telemetry/history`
- Measurement: `telemetry_point` with source timestamps preserved on write
- Bounds: `hours` 1–168, `limit` 1–2000, aggregate windows whitelist
- Flux tag sanitization prevents injection
- Point filter validates registry ownership before query
- Live mode returns empty series + typed state (`NO_DATA`, `INFLUX_UNAVAILABLE`) — no demo fallback

---

## 4. Registry Data Health

- Building health prefers `list_building_current()` registry points
- Per-point drilldown: `GET /data-health/points/{point_id}`
- Exposes identity, source, value, quality, timestamps, freshness, interval, state
- Missing values → OFFLINE/UNKNOWN — not fabricated percentages

---

## 5. Edge Collection Transition

`mapped_points.json` remains **bootstrap/fallback only**.

Production lifecycle:

1. Metasys discovery populates registry
2. Operator approves semantic mappings in UI/API
3. Edge loads `GET /gateways/{id}/collection-config` via `GATEWAY_API_KEY`
4. If neither bootstrap nor approved config exists → `NOT_CONFIGURED` heartbeat

Edge never auto-collects all discovered points.

---

## 6. Known Limitations

- Tag Mapper UI not yet wired to Phase 4 semantic APIs (API hooks exist)
- Influx history requires live edge telemetry with numeric values
- Gateway token issuance still requires master key (by design — ops-only)
- Lovable ingest-gated mode uses anon key + backend API gate (no Supabase dashboard)

---

## 7. Pilot Blockers (customer-site)

- Real Metasys credentials on edge host
- Edge Docker deployment with `GATEWAY_API_KEY`
- Initial semantic mapping approval for target building
- Live telemetry flowing to Influx (`DEMO_MODE=false`)

---

## 8. Recommended Phase 5

- Wire Tag Mapper UI to semantic suggestion/approval APIs
- Certificate-based gateway identity (mTLS)
- Per-point Influx chart drilldown in Live Telemetry
- Automated semantic auto-approve workflow with audit trail export
