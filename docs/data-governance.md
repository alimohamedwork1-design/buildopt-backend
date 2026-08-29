# Data Governance (PDPL Foundation)

**Last updated:** 2026-08-29  
UAE **Personal Data Protection Law (PDPL)** alignment — foundation for pilot and enterprise contracts.

> This document establishes policy intent. Legal review required before customer-facing DPA.

## Scope

BuildOpt processes:

| Data class | Examples | Sensitivity |
|------------|----------|-------------|
| **Building operational** | HVAC kW, temperatures, alarms | Commercial — tenant building data |
| **Account / identity** | Email, name, role | Personal data (PDPL) |
| **BMS credentials** | Metasys username/password | Critical secret — encrypted at rest |
| **Audit / session** | Login events, API sessions | Operational + personal |

Building telemetry is generally **not** personal data unless tied to identifiable individuals (e.g. named occupant feedback). Treat occupant/tenant modules (`/tenant`, `/occupant-feedback`) as higher sensitivity.

## Tenant ownership model

| Entity | Owner | Storage |
|--------|-------|---------|
| Organization / client | Customer account | `profiles.account_mode`, Supabase `profiles` |
| Buildings | Customer | `public.buildings` (RLS by org) |
| Points & connections | Customer | `building_points`, `building_connections` |
| Telemetry time-series | Customer (processor: BuildOpt) | InfluxDB bucket per deployment |
| Alerts & work orders | Customer | Supabase tables + RLS |

**Processor role:** BuildOpt AI acts as data processor for building operators; customer is controller for site data.

Cross-tenant isolation:

- Backend: `UserContext.building_ids`, `assert_building_access()` in `app/deps/guards.py`
- Database: Supabase RLS policies in `buildopt-ai/supabase/migrations/*`
- Gap: not all API routes enforce tenant scope (see `docs/security-model.md`)

## Data residency

| Service | Default region | Note |
|---------|----------------|------|
| Supabase | Project-selected (current: cloud) | Confirm UAE/GCC residency with customer |
| InfluxDB Cloud | `us-east-1` in `railway.env.template` | **Action:** migrate to nearest region for pilot |
| Railway API | US/EU (Railway) | API holds ephemeral cache only |
| Edge agent | On-prem building LAN | Data exits site only via HTTPS ingest |

For strict UAE residency requirements, document actual Supabase/Influx regions in customer DPA.

## Retention policy (target)

| Data type | Retention | Mechanism | Status |
|-----------|-----------|-----------|--------|
| Raw telemetry (Influx) | **24 months** rolling | Bucket retention rules | PLANNED — configure in Influx |
| Aggregated KPIs | 36 months | Downsample tasks | PLANNED |
| Alerts (Supabase) | 12 months active; archive 24 months | Scheduled cleanup job | PLANNED |
| Audit logs | 24 months | `app/services/audit_log.py` → future Supabase table | PARTIAL (stdout only) |
| Session analytics | 90 days | `app/api/sessions.py` | PARTIAL |
| Demo/simulated data | Session only | Not persisted when `DEMO_MODE=false` | COMPLETE |

## PDPL principles mapping

| Principle | BuildOpt control |
|-----------|------------------|
| Lawfulness / purpose limitation | Collect only BMS ops + account data needed for service |
| Data minimization | Map logical keys only; no gratuitous point export |
| Accuracy | `app/services/data_quality.py` — GOOD/STALE/INVALID |
| Storage limitation | Retention table above |
| Security | Encryption in transit (HTTPS), Supabase RLS, credential encryption |
| Accountability | Audit log scaffold; DPA + subprocessors list TBD |

## Subject rights (process)

| Right | BuildOpt process |
|-------|------------------|
| Access | Export via admin API / Supabase dashboard (TBD self-service) |
| Rectification | Profile edit in app; building data via facility manager |
| Erasure | Delete user → cascade `profiles`, revoke JWT; building delete TBD |
| Portability | CSV/Excel export via reports module (PARTIAL) |

**SLA target:** 30 days for verified requests (configure in customer contract).

## Subprocessors (document for DPA)

| Vendor | Purpose |
|--------|---------|
| Supabase | Auth, Postgres, Realtime, Edge Functions |
| InfluxData | Time-series storage |
| Railway | API hosting |
| Lovable / hosting | Frontend CDN |
| Google (Gemini) / Lovable AI Gateway | AI insights (when enabled) |

## Demo vs live data

- `DEMO_MODE=true`: synthetic HQ Tower data — **not** customer data; safe for sales demos.
- Live accounts (`account_mode=live`): `data_policy.py` forbids simulated telemetry injection.
- Never mix demo and live tenant data in same Influx bucket without tagging.

## Related

- `docs/security-model.md` — RBAC, RLS
- `docs/production-readiness-audit.md` § Multi-Tenant Domain Model
- UAE PDPL Federal Decree-Law No. 45 of 2021
