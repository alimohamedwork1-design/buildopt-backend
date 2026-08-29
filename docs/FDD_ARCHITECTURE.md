# FDD Architecture — Phase 6–7 Foundation

## Pipeline

```
Approved Semantic Mappings
    → build_semantic_readings()
    → validate_fdd_inputs()  (READY | PARTIAL | BLOCKED | INSUFFICIENT_DATA)
    → FddRuleEngine.evaluate_equipment()
    → FddFaultStore (deduplicated persistence)
    → GET /fdd/buildings/{id}/faults
```

## Rule framework

Rules defined in `fdd_rule_framework.py` with explicit:

- `required_inputs` / `optional_inputs`
- threshold + check function
- severity + persistence policy
- evidence contract on every fault

**No diagnosis when inputs are missing** — rule returns blocked/not evaluable.

## AHU rules (Phase 7 initial)

AHU-001 through AHU-010 — SAT deviation, setpoint tracking, simultaneous heat/cool, valve leakage, fan mismatch, filter DP, static pressure, OA damper, MAT inconsistency, sensor flatline.

## Fault lifecycle

`DETECTED` → `INVESTIGATING` → `CONFIRMED` → `SUPPRESSED` → `RESOLVED` → `CLOSED`

Transitions via `POST /fdd/faults/{id}/transition` with audit trail.

## Deduplication

Fault ID = `{rule_id}:{equipment_id}` — upsert updates `last_seen`, preserves `first_seen`.

## Not implemented yet

- Full chiller/pump/CT/FCU rule libraries (Phase 8)
- ML/anomaly diagnosis
- Autonomous writeback
- Customer-site validation (BLOCKED_REAL_SITE)
