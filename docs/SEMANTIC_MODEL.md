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

## Mapping pipeline (Phase 4 — Registry V2)

DISCOVER → REGISTRY → SUGGEST → REVIEW → APPROVE → COLLECTION CONFIG → EDGE

| Step | Endpoint |
|------|----------|
| Registry | `POST /discovery/points/batch` |
| Suggestions | `GET /semantic/buildings/{id}/suggestions` |
| Approval | `POST /semantic/buildings/{id}/approve` |
| Edge export | `GET /gateways/{gateway_id}/collection-config` |

Code: `semantic_mapping_service.py`, `semantic_mapper.py`, `metasys_auto_mapper.py`  
Thresholds: ≥0.95 auto-candidate, 0.75–0.95 review, <0.75 unmapped — **never auto-approved without explicit POST**

---

## Canonical names

ahu.supply_air_temperature, chiller.cop, zone.temperature, energy.power_kw, etc.

Preserve vendor names alongside canonical names in UI and exports.
