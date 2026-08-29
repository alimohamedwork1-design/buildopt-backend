# Vendor-Neutral Semantic Model

BuildOpt sits above the BMS — it does not replace Metasys, OpenBlue, or field controllers.

---

## Entity hierarchy

Portfolio → Site → Building → Floor / Space / Zone → System → Equipment → Point

Also: Meter, Controller, Gateway/Edge

---

## Equipment types (minimum)

AHU, FCU, VAV, Chiller, CoolingTower, CHWP, CWP, Boiler, Pump, Fan, DXUnit, VRF, EnergyMeter, WaterMeter, TemperatureSensor, PressureSensor, HumiditySensor

Refrigeration vertical uses separate semantics (compressor, evaporator, NH3 safety).

---

## Canonical points table

`public.canonical_points` — see migration `20260829120000_building_lifecycle_canonical_points.sql`

---

## Mapping pipeline (Phase 5 — Operations)

DISCOVER → REGISTRY → SUGGEST → REVIEW → APPROVE → PUBLISH CONFIG → EDGE → HISTORY

| Step | Endpoint |
|------|----------|
| Registry | `POST /discovery/points/batch` |
| Review queue | `GET /semantic/buildings/{id}/review-queue` |
| Approve / reject / edit / revert | `POST /semantic/buildings/{id}/approve|reject|edit|revert` |
| Audit | `GET /semantic/buildings/{id}/audit` |
| Publish config | `POST /semantic/buildings/{id}/collection-config/publish` |
| Edge export | `GET /gateways/{gateway_id}/collection-config` |
| Point history | `GET /buildings/{id}/telemetry/history?point_id=` |

Semantic metadata lives in `raw_points.metadata` (never mutates raw source identity).

Relationships supported in metadata: `has_point`, `serves`, `located_in`, `controlled_by`, `feeds`, `meters`.

See `docs/SEMANTIC_OPERATIONS.md` for workflow and RBAC.

---

## Canonical names

ahu.supply_air_temperature, chiller.cop, zone.temperature, energy.power_kw, etc.

Preserve vendor names alongside canonical names in UI and exports.
