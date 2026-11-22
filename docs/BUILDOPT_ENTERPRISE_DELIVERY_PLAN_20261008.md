# BuildOpt AI — Enterprise Delivery Master Plan
Date: 2026-10-08
Status: PLANNING / EXECUTION KICKOFF — no product fixes claimed complete.
Repositories: alimohamedwork1-design/buildopt-backend and alimohamedwork1-design/buildopt-ai

## Execution principles
- Preserve existing production functions, APIs, tenants, and integrations.
- Never display simulated, synthetic, or heuristic values as measured live building data.
- Default BMS access READ_ONLY; no physical writeback without documented site authorization, controls safety review, human approval, and rollback testing.
- Develop on isolated branches, pass tests, review diffs, and merge in dependency order.
- Report VERIFIED, PARTIAL, BLOCKED and NOT STARTED explicitly; no fabricated completion claims.

## Phase 1 — P0 Stabilization and security
1. Reproduce and repair frontend npm ci/lockfile failure; ensure lint, typecheck, unit tests and build pass in CI.
2. Review open frontend PRs #1/#2 and backend PR #1 against current main; rebase/cherry-pick safely, resolve conflicts, do not blindly merge.
3. Remove tracked frontend .env where appropriate, verify no private credentials were committed, rotate any exposed secrets, enforce .env.example and secret scanning.
4. Audit Supabase RLS, backend authentication, tenant scoping, role escalation, and production CORS.
Exit: CI green for both repositories; credential audit and access-control tests pass.

## Phase 2 — P0 Live-data truth
1. Audit all API responses and frontend pages for mock fallback in live mode.
2. Remove fabricated history, constant confidence, baseline multiplier, default optimization scores, static work order KPIs and fictitious savings from live paths.
3. Implement clear NO_DATA / INSUFFICIENT_DATA / STALE / DEGRADED states with provenance and timestamps.
4. Ensure immutable data provenance: tenant, building, equipment, point, timestamp, units, quality, source, model version.
5. Split potential vs modeled vs measured vs verified savings and forbid unsupported ROI claims.
Exit: disconnected building produces no fabricated live readings; golden integration tests.

## Phase 3 — P0 FDD and AI
1. Fix mismatched rule checkers for chiller CH-003, pump PUMP-001, tower, FCU and VAV rule mappings.
2. Add positive/negative/boundary and missing-data tests for every FDD rule; validate persistence, preconditions, confidence, hysteresis, deduplication and suppression.
3. Add engineering rule versioning and traceable evidence.
4. Replace static assistant conclusions with evidence-based retrieval, explicit limitations, confidence calibration and tenant-safe tool calls.
Exit: rule suite covers all defined rules and assistant never asserts unverified facts.

## Phase 4 — P0/P1 BMS and Edge
1. Validate Metasys REST authentication, object inventory, trends, paging, reconnect, API versions and read-only permissions at an authorized test site.
2. Implement and test BACnet/IP, Modbus TCP, OPC-UA and MQTT connectors (current modern edge placeholders must not be advertised live).
3. Build approved mapping wizard, Brick/Haystack semantic tags, unit conversions, data quality and stale point detection.
4. Gateway heartbeat, offline store-and-forward, retries, bounded queues, certificate rotation, fleet status and remote updates.
Exit: hardware-in-loop or vendor simulator contract tests; at least 7 days stable pilot ingestion before site readiness signoff.

## Phase 5 — P1 Enterprise administration
1. Platform admin vs tenant admin vs building admin separation; RBAC and least privilege enforced server-side.
2. Organization, portfolio, building, asset, user invite/approval, role, site assignment, module entitlements and subscription plan lifecycle.
3. Account status, audit logs, session revocation, MFA readiness, quotas, billing hooks and tenant isolation regression suite.
4. Guided in-product help for each administrative action and unobtrusive AI suggestions.
Exit: cross-tenant access negative tests pass; onboarding/offboarding acceptance tests.

## Phase 6 — P1 Operations
1. FDD fault lifecycle: detected, triaged, assigned, acknowledged, resolved, verified, closed.
2. Work order CRUD, real metrics, assignment, evidence, SLA escalation, notifications, maintenance history and optional CMMS connectors.
3. Suppression and duplicate fault handling; equipment impact prioritization.
Exit: complete fault-to-closure workflow tested against real persistent records.

## Phase 7 — P1 Energy and optimization
1. Meter and tariff configuration per utility, site, effective date and demand structure; avoid hardcoded universal tariff claims.
2. Weather/occupancy-normalized baseline, independent reporting periods, M&V evidence and uncertainty.
3. Replace placeholder LSTM/MPC claims with validated history-based forecasting and shadow-only constrained recommendations; holdout MAE/RMSE and model registry.
4. Human approval and safety gating design for any future controlled writeback; no enablement by default.
Exit: measurable pilot KPIs, verified provenance, reproducible forecasting benchmark.

## Phase 8 — P2 UX, reporting and field mobile
1. Consolidate production navigation and distinguish production/pilot/heuristic/simulated/concept modules.
2. Role-based dashboards, responsive mobile field workflow, offline drafts and conflict-safe synchronization.
3. PDF/CSV exports with source, date range, data sufficiency, disclaimer and audit.
4. Arabic/English RTL, accessibility, onboarding wizard and contextual tooltips.
Exit: E2E tests for key user journeys on desktop and mobile.

## Phase 9 — Release, pilot, and security
1. CI/CD gates, staging, database migration rollback, observability, SLOs, alerting, backups and restore drills.
2. Load testing, penetration review, network threat model, secrets management, incident playbooks.
3. Site commissioning acceptance with point mapping, alarm testing, 7-day telemetry reliability and signoff.
4. Post-deployment 14+ day monitoring for savings verification where measurement protocol allows; longer periods when required.
Exit: signed pilot checklist, reproducible deploy and rollback, no open P0 defects.

## Backlog / deferred until pilot
Digital twin, Ramadan/sandstorm schedules, chiller plant advanced optimization, SAP/Maximo integration, fleet-scale benchmarking. Quantum optimization, carbon marketplace and drone modules remain CONCEPT unless independently implemented and validated.

## First engineering task
Start with the frontend CI dependency-lock mismatch and the current backend/frontend hardening PR review. Do not merge or deploy before passing gates.

## Progress ledger
- [x] Roadmap documented in isolated branch.
- [ ] Phase 1 engineering changes and CI verification.
- [ ] Phase 2
- [ ] Phase 3
- [ ] Phase 4
- [ ] Phase 5
- [ ] Phase 6
- [ ] Phase 7
- [ ] Phase 8
- [ ] Phase 9
