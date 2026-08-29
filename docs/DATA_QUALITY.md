# Data Quality Engine — Phase 6

## Normalized quality states

`GOOD` · `UNCERTAIN` · `BAD` · `STALE` · `NO_DATA` · `INVALID` · `OUT_OF_RANGE` · `FLATLINE` · `TIMESTAMP_ERROR`

Quality is **never fabricated** when evidence is unavailable.

## Scoring components

Each point score exposes:

- availability
- freshness
- completeness
- validity
- range_check
- flatline
- timestamp_integrity
- sampling_consistency
- unit_consistency
- outlier_rate

Overall score = weighted average of components (0–100).

## Historical quality

Influx `telemetry_point` writes include `quality` and `source_quality` fields (Phase 3+ pipeline).

Historical overlay is available **only when quality was stored at ingest time**. Older samples without quality metadata report `quality_available: false`.

## Aggregation

Point → Equipment → Building via `aggregate_scores()`.

## Limitations

- 7-day Influx history cap (168h)
- Pre-Phase-6 samples lack per-sample quality in Influx
- Noise/drift/outlier components require sufficient sample windows
