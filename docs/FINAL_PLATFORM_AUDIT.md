# Final Platform Audit — BuildOpt (Exhaustive Phase 18)

**Date:** 2026-08-29  
**Backend baseline:** `1ff1403` → productization pass  
**Scope:** Phases 1–18 production path + software-only closure

## A. Production data path (verified)

```
Metasys → Edge → Gateway Auth → Discovery → Raw Registry → Semantic Mapping
  → Approved Collection Config → Telemetry Pipeline → Influx (quality fields)
  → Historical Quality → Data Health → FDD (quality gate) → Baseline
  → Recommendations (durable) → Savings/M&V (durable) → Shadow Optimization
  → AI Assistant (tool API) → Reports
```

| Stage | Input | Output | Tenant scope | Durability | Live fallback |
|-------|-------|--------|--------------|------------|---------------|
| Gateway auth | Token | Scoped ingest | tenant/building | Supabase tokens | None |
| Semantic | Raw points | Approved mappings | building RBAC | Supabase + audit | None in live |
| Telemetry | Edge batch | Influx rows + state | tenant/building | Influx + SQLite/Supabase | Reject bad quality |
| Historical quality | Influx series | Per-sample quality overlay | building | Influx `quality` field | Honest NO_DATA |
| FDD | Semantic readings | Faults + evidence | building | SQLite/Supabase fdd_faults | BLOCKED if inputs bad |
| Recommendations | Faults | Lifecycle records | building RBAC | SQLite/Supabase | Empty list |
| Savings/M&V | Baseline + measure | POTENTIAL≠VERIFIED | building RBAC | SQLite/Supabase | INSUFFICIENT_DATA |
| Shadow opt | Setpoints + baseline | Candidates only | building | Ephemeral | SHADOW_ONLY |
| Writeback | Request | Queued NOT executed | site allowlist | Audit log | READ_ONLY default |
| AI Assistant | Tool query | Evidence JSON | building access | N/A | No Supabase LLM in live |
| Reports | Live APIs | Honest limitations | building RBAC | Generated on read | Incomplete OK |

## B. Software-only closures (this pass)

| Item | Status |
|------|--------|
| Durable recommendations + audit + RBAC | **PASS** |
| Durable savings/M&V + transition gates | **PASS** |
| Shadow optimization UI (live) | **PASS** |
| Writeback safety UI (READ ONLY) | **PASS** |
| AI Assistant live → backend tools | **PASS** |
| Reports live wiring | **PASS** |
| Baseline v2 feature exposure | **PASS** |
| Observability counters expanded | **PASS** |
| Historical quality from Influx field | **PASS** (fixed query) |
| GCC configurable tariffs/calendar | **PASS** |
| Migration 011 applied (Lovable Cloud) | **PASS** |

## C. Frontend live audit (core modules)

| Page | Classification | Live behavior |
|------|----------------|---------------|
| Tag Mapper | PASS | Live API |
| Live Telemetry | PASS | Live API / empty |
| Data Health | PASS | Live API |
| FDD Engine | PASS | Live faults API |
| AI Recommendations | PASS | Live API / empty |
| ROI / Savings | PASS | Potential vs Verified split |
| Optimization | PASS | Shadow mode banner |
| Setpoint Writeback | PASS | Status only, no commands |
| Reports | PASS | Live report APIs |
| AI Chat Assistant | PASS | Backend tools in live |
| System Status | PARTIAL | Backend health live; service uptime list still demo template |
| LABS / simulation modules | SAFE_DEMO_ONLY | Gated |

## D. Security

| Check | Result |
|-------|--------|
| Tenant building access guards | PASS |
| Gateway → master endpoint block | PASS (Phase 5) |
| Viewer → recommendation approve | BLOCKED (403) |
| Viewer → savings verify | BLOCKED (403) |
| WRITEBACK_ENABLED default false | PASS |
| AI cross-tenant (building_id guard) | PASS |

## E. Database

Migrations 001–011. Do not rewrite applied migrations.  
011 extends recommendations/savings with audit tables.

## F. Remaining PARTIAL (software)

- SystemStatus synthetic service uptime cards (cosmetic; backend health is real)
- LABS-tier modules intentionally demo/simulation
- Baseline weather normalization: features exposed, linear model not applied (documented)

## G. BLOCKED_REAL_SITE

- Real Metasys connection + discovery
- Edge host 7-day ingest validation
- Customer FDD rule engineering sign-off
- Verified savings with real measurement period

## Verdict

**CODE_READY / PILOT_READY_WITH_SITE_BLOCKERS**

All software-only productization items addressed. Customer-site validation remains the only path to PILOT_VALIDATED.
