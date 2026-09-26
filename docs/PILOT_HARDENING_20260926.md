# Pilot Hardening — 2026-09-26

## Security closure

The legacy direct JCI/Metasys command route now passes through the global READ_ONLY write policy. In pilot mode it cannot execute a network write.

Sensitive JCI configuration/diagnostic/raw-object operations require an authenticated BMS configuration role. Anonymous callers receive 401 and unauthorized roles receive 403.

## CI

CI now installs `pytest-asyncio` and separates:
- full DEMO-mode regression coverage, and
- production-mode trust/security/data-integrity coverage.

Latest branch run: both demo and production scopes must pass before merge.

## Pilot control posture

- Default write mode: `READ_ONLY`
- Default control maturity: `L0_MONITOR`
- Shadow optimization is allowed.
- Recommendations are advisory.
- Physical BMS write-back requires a future human-approval workflow, site allowlist, change control, read-back verification, and audit.

## Product truth

Current production integration path is Metasys REST and/or the BuildOpt edge gateway. A direct OpenBlue cloud/API connector is not considered live or validated by this backend.

## Remaining real-site blockers

1. Customer site credentials/network.
2. Discovery + approved semantic mapping.
3. Sustained live ingest validation.
4. Customer FDD engineering sign-off.
5. M&V measurement period for verified savings.
