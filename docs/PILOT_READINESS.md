# Pilot Readiness

pilot_ready: false (2026-08-29)

---

## Blockers

- B1: Real Metasys credentials/network
- B2: Railway DEMO_MODE=false + InfluxDB
- B3: Pilot building selected

---

## Critical checks

- [ ] Zero simulated telemetry in live mode (partial — backend fixed, some pages use mock-data directly)
- [ ] Tenant isolation tests pass
- [ ] Real building in Supabase
- [ ] Metasys connection test passes
- [ ] Points discovered and mapped
- [ ] InfluxDB persistence verified
- [ ] UI shows latest + history with provenance
- [ ] Stale/offline typed states
- [ ] FDD on real mapped points
- [ ] Write-back disabled (PASS)
- [ ] Audit logging active (partial)

---

## Control maturity default

L0 MONITOR / L1 RECOMMEND only

Full checklist: `docs/pilot-readiness-checklist.md`
