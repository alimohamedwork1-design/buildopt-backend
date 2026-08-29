# Semantic Operations — Phase 5

Engineer-facing workflow for discovery → review → approval → collection config → edge refresh.

## Workflow

```text
Edge Discovery
    → POST /discovery/points/batch (raw registry)
    → GET  /semantic/buildings/{id}/review-queue
    → POST /semantic/buildings/{id}/approve|reject|edit|revert
    → POST /semantic/buildings/{id}/collection-config/publish
    → GET  /gateways/{id}/collection-config (edge, gateway token)
    → GET  /buildings/{id}/telemetry/history?point_id=… (point drilldown)
```

## Review queue

`GET /api/v1/semantic/buildings/{building_id}/review-queue`

| Filter | Query param |
|--------|-------------|
| Status | `status=UNMAPPED|SUGGESTED|REVIEW_REQUIRED|APPROVED|REJECTED` |
| Equipment | `equipment=AHU-01` |
| Source | `source=metasys` |
| Min confidence | `min_confidence=0.8` |

Summary buckets (UI default groups):

- **High confidence** — `SUGGESTED` with confidence ≥ 0.85
- **Review required** — `REVIEW_REQUIRED` or low-confidence suggestions
- **Unmapped** — no semantic key
- **Approved / Rejected** — explicit engineer decisions

## Approval rules (pilot)

- Human review is the default; no bulk auto-approve.
- Approvals below confidence 0.70 are rejected server-side (`confidence_too_low_for_approval`).
- Raw source identity (`source_point_id`, `source_name`, vendor path) is **immutable**; only semantic metadata is edited.
- Cross-building approve attempts return `source_point_not_found` (no information leak).

## Actions

| Action | Endpoint | RBAC |
|--------|----------|------|
| Approve | `POST …/approve` | Engineer/Admin roles |
| Reject | `POST …/reject` | Engineer/Admin |
| Edit | `POST …/edit` | Engineer/Admin |
| Revert | `POST …/revert` | Engineer/Admin |
| Publish config | `POST …/collection-config/publish` | Engineer/Admin |
| Read queue / audit | GET endpoints | Viewer+ |

Roles with write access: `admin`, `bms_integrator`, `energy_engineer`, `facility_manager`.

## Audit trail

Table: `semantic_audit_log` (migration 009)

Every action records: `audit_id`, `point_id`, `action`, `previous_state`, `new_state`, `actor_user_id`, `actor_email`, `comment`, `confidence`, `created_at`.

Actions: `SUGGESTED`, `EDITED`, `APPROVED`, `REJECTED`, `REVERTED`.

`GET /api/v1/semantic/buildings/{building_id}/audit?point_id=…`

## Collection config versioning

Table: `collection_config_versions` (migration 009)

| Field | Description |
|-------|-------------|
| `config_version` | UUID version id |
| `status` | `DRAFT` · `ACTIVE` · `SUPERSEDED` |
| `mapping_revision` | Monotonic revision |
| `point_count` / `approved_count` / `unmapped_count` | Registry stats at publish time |
| `config_payload` | Approved mapping JSON (no secrets) |

Edge compares `config_version` on periodic refresh; on failure keeps last known active config.

## UI modules

| Module | Phase 5 behaviour |
|--------|-------------------|
| **Tag Mapper** | Live review queue, approve/reject/edit/revert, collection config panel, FDD readiness |
| **PointDetailsPanel** | Shared drilldown: identity, history, audit, data health |
| **Live Telemetry** | Click mapped point → PointDetailsPanel |
| **Data Health** | Click registry row → PointDetailsPanel |

## Zero-mock-live

In live data mode the semantic UI never shows fabricated points, confidence, equipment, history, or audit events. Empty states: `NO DATA`, `NOT CONFIGURED`, `INFLUX UNAVAILABLE`, `permission denied`.

## Known limitations

- Historical Influx samples do not store per-point quality metadata; quality overlay applies to current state only.
- History query max window: **168h (7d)** — backend enforced; 30d not available until retention/query limits are raised.
- Relationship editing is API-supported; full graph UI deferred.
