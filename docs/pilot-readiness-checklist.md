# Pilot Readiness Checklist

**Last updated:** 2026-08-29  
Machine-readable checklist derived from master productionization prompt v1.0.

```yaml
# buildopt-pilot-readiness v1.0
meta:
  version: "1.0"
  date: "2026-08-29"
  repos:
    - buildopt-ai
    - buildopt-backend
  target: "single-building GCC pilot (Metasys-first)"
  overall_status: PARTIAL

blockers:
  - id: B1
    item: Real Metasys credentials and network path
    owner: customer_it
    status: OPEN
  - id: B2
    item: Production InfluxDB + Supabase keys on Railway
    owner: ops
    status: OPEN
  - id: B3
    item: Destructive migration approval
    owner: engineering
    status: OPEN

phases:
  - id: phase_0_audit
    name: Repository and production-readiness audit
    status: PASS
    items:
      - id: P0-01
        check: production-readiness-audit.md complete
        status: PASS
        evidence: docs/production-readiness-audit.md
      - id: P0-02
        check: Backend pytest baseline recorded
        status: PASS
        evidence: 45+ passed (see production-verification.md)
      - id: P0-03
        check: Frontend build passes
        status: PASS
        evidence: npm run build

  - id: phase_1_data_integrity
    name: Data integrity — no silent demo in live mode
    status: PARTIAL
    items:
      - id: P1-01
        check: Typed error models (DEMO_DATA_FORBIDDEN, NO_TELEMETRY, etc.)
        status: PASS
        evidence: app/models/errors.py
      - id: P1-02
        check: Central data policy service
        status: PASS
        evidence: app/services/data_policy.py
      - id: P1-03
        check: module_data_service returns empty_state for live without telemetry
        status: PASS
        evidence: tests/test_data_integrity.py
      - id: P1-04
        check: live_data_service no silent demo fallback
        status: PASS
        evidence: tests/test_live_data_production.py
      - id: P1-05
        check: Frontend pickApiOrMockStrict used on all priority pages
        status: PARTIAL
        evidence: src/lib/data-source.ts — pickApiOrMock still has live fallback
      - id: P1-06
        check: DEMO_MODE=false end-to-end API matrix test
        status: PARTIAL
        evidence: partial coverage only

  - id: phase_2_auth_tenant
    name: Auth, RBAC, tenant isolation
    status: PARTIAL
    items:
      - id: P2-01
        check: Supabase JWT validation
        status: PASS
        evidence: app/deps/auth.py
      - id: P2-02
        check: UserContext with building_ids and enabled_modules
        status: PASS
        evidence: app/models/user_context.py
      - id: P2-03
        check: Route guards on all data endpoints
        status: PARTIAL
        evidence: app/deps/guards.py — not all routers wired
      - id: P2-04
        check: Supabase RLS policies audited
        status: PARTIAL
        evidence: buildopt-ai/supabase/migrations/*
      - id: P2-05
        check: Cross-tenant integration test
        status: PARTIAL
        evidence: tests/test_account_platform.py

  - id: phase_3_onboarding
    name: Building onboarding and lifecycle
    status: PARTIAL
    items:
      - id: P3-01
        check: Building CRUD API
        status: PASS
        evidence: app/api/buildings.py
      - id: P3-02
        check: Lifecycle enum (DRAFT→ACTIVE)
        status: PARTIAL
        evidence: supabase/migrations/005_building_lifecycle.sql
      - id: P3-03
        check: Excel point import
        status: PARTIAL
        evidence: app/services/excel_import.py — openpyxl missing on Railway
      - id: P3-04
        check: Onboarding wizard UI
        status: FAIL
        evidence: not implemented
      - id: P3-05
        check: Activate building gate (form ≠ active)
        status: FAIL
        evidence: audit finding

  - id: phase_4_metasys
    name: Metasys REST integration
    status: PARTIAL
    items:
      - id: P4-01
        check: test-connection live probe
        status: PASS
        evidence: app/api/jci.py POST /test-connection
      - id: P4-02
        check: Credential save to Supabase
        status: PASS
        evidence: connection_store, 002_bms_connections.sql
      - id: P4-03
        check: Auto-map and poll cycle
        status: PASS
        evidence: metasys_auto_mapper.py, pipeline.run_poll_cycle
      - id: P4-04
        check: Production E2E with real site
        status: FAIL
        evidence: blocker B1
      - id: P4-05
        check: VPN/tunnel to private Metasys
        status: PARTIAL
        evidence: PRODUCTION.md — manual Cloudflare Tunnel

  - id: phase_5_edge_ingest
    name: Edge gateway and ingestion
    status: PARTIAL
    items:
      - id: P5-01
        check: Ingest API with INGEST_API_KEY
        status: PASS
        evidence: app/api/ingest.py, tests/test_ingest_production.py
      - id: P5-02
        check: Edge agent Docker deploy
        status: PARTIAL
        evidence: edge/DEPLOY.md
      - id: P5-03
        check: InfluxDB persistence from poll/ingest
        status: PARTIAL
        evidence: app/services/influx_client.py
      - id: P5-04
        check: Data quality states (GOOD/STALE)
        status: PARTIAL
        evidence: app/services/data_quality.py — not wired to all paths
      - id: P5-05
        check: BACnet live read (non-demo)
        status: FAIL
        evidence: bacnet_client placeholder

  - id: phase_6_fdd
    name: FDD rule engine
    status: PARTIAL
    items:
      - id: P6-01
        check: Rule engine with prerequisites
        status: PASS
        evidence: app/ml/fault_detector.py
      - id: P6-02
        check: NOT_EVALUABLE when points missing
        status: PASS
        evidence: fault_detector.evaluate()
      - id: P6-03
        check: FDD pipeline job 60s
        status: PASS
        evidence: pipeline.run_fdd_cycle
      - id: P6-04
        check: Alert webhook to Supabase
        status: PARTIAL
        evidence: supabase/functions/sync-bms-alert/
      - id: P6-05
        check: Full rule catalog (26+)
        status: FAIL
        evidence: 7 rules in code

  - id: phase_7_writeback
    name: Write-back safety
    status: PARTIAL
    items:
      - id: P7-01
        check: READ_ONLY default
        status: PASS
        evidence: app/services/write_policy.py
      - id: P7-02
        check: COMMAND_NOT_ALLOWED on write routes
        status: PARTIAL
        evidence: jci/command not fully gated
      - id: P7-03
        check: Approval workflow
        status: FAIL
        evidence: planned only
      - id: P7-04
        check: Audit log for commands
        status: PARTIAL
        evidence: app/services/audit_log.py — stdout only

  - id: phase_8_documentation
    name: Production documentation pack
    status: PASS
    items:
      - id: P8-01
        check: docs/ architecture and integration pack
        status: PASS
        evidence: docs/*.md (this release)
      - id: P8-02
        check: Module data source matrix
        status: PASS
        evidence: docs/module-data-source-matrix.md
      - id: P8-03
        check: Pilot and verification checklists
        status: PASS
        evidence: docs/pilot-readiness-checklist.md

  - id: phase_9_railway
    name: Railway deployment hardening
    status: PARTIAL
    items:
      - id: P9-01
        check: railway.toml healthcheck
        status: PASS
        evidence: /api/v1/health
      - id: P9-02
        check: Env template without committed secrets
        status: PASS
        evidence: railway.env.template
      - id: P9-03
        check: Lean deps include pilot features
        status: FAIL
        evidence: requirements-railway.txt gaps
      - id: P9-04
        check: Scheduler single-instance or lock
        status: FAIL
        evidence: APScheduler in-process

  - id: phase_10_pilot_go_live
    name: Pilot go-live verification
    status: PARTIAL
    items:
      - id: P10-01
        check: DEMO_MODE=false on Railway
        status: FAIL
        evidence: production still demo_mode=true
      - id: P10-02
        check: Live telemetry visible in UI
        status: FAIL
        evidence: blocker B1
      - id: P10-03
        check: verify-production.ps1 all green
        status: PARTIAL
        evidence: scripts/verify-production.ps1
      - id: P10-04
        check: PDPL / data governance doc
        status: PASS
        evidence: docs/data-governance.md
      - id: P10-05
        check: Customer sign-off checklist
        status: FAIL
        evidence: pending pilot selection

go_live_minimum:
  required_pass:
    - P1-03
    - P1-04
    - P4-01
    - P4-03
    - P5-01
    - P7-01
    - P9-01
  required_with_blockers_closed:
    - P4-04
    - P10-01
    - P10-02
```

## Human summary

| Gate | Status |
|------|--------|
| Demo platform ready | YES |
| Live single-building pilot | **NO** — blockers B1–B3 |
| Documentation pack | YES |
| Safe write-back | YES (disabled by default) |

See `docs/production-verification.md` for command-level evidence.
