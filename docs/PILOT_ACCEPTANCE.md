# Pilot Acceptance — BuildOpt

## Automated checks

Run: `python scripts/pilot_verify.py`

## Acceptance criteria

| # | Criterion | Automated | Site required |
|---|-----------|-----------|---------------|
| 1 | Metasys connection possible | — | YES |
| 2 | Real discovery | — | YES |
| 3 | Raw points registered | API | YES |
| 4 | Semantic review operational | API | Partial |
| 5 | Approved config published | API | YES |
| 6 | Edge config refresh | Edge | YES |
| 7 | Telemetry ingestion | API | YES |
| 8 | No simulated LIVE data | Code scan | — |
| 9 | History works (≤7d) | API | YES |
| 10 | Data Health works | API | Partial |
| 11 | Equipment readiness | API | Partial |
| 12 | FDD runs when inputs support | API | YES |
| 13 | Faults include evidence | Unit tests | Partial |
| 14 | Recommendations trace to faults | Unit tests | Partial |
| 15 | Baseline exposes confidence | Unit tests | — |
| 16 | Potential ≠ verified savings | Unit tests | — |
| 17 | Reports use live data | API | Partial |
| 18 | AI Assistant uses real tools | API | Partial |
| 19 | Audit trail works | Phase 5 tests | Partial |
| 20 | Autonomous writeback OFF | Unit tests | — |

## BLOCKED_REAL_SITE

Items marked YES require customer Metasys credentials, edge host, and 7-day ingest.
