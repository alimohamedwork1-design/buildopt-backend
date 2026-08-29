# Point Mapping

**Last updated:** 2026-08-29  
Canonical telemetry model, Metasys fuzzy mapping, and Excel import.

## Canonical point model

BuildOpt normalizes BMS data to **logical keys** independent of vendor object IDs.

### HVAC logical keys

Defined in `app/services/metasys_auto_mapper.py` → `LOGICAL_KEYS`:

| Logical key | Description |
|-------------|-------------|
| `supply_air_temp` | AHU / CHW supply air temperature (°C) |
| `return_air_temp` | Return air temperature (°C) |
| `hvac_power_kw` | HVAC or chiller electrical power (kW) |
| `total_kw` | Whole-building or main meter (kW) |
| `temp_c` | Zone / space temperature (°C) |
| `co2_ppm` | Indoor CO₂ (ppm) |
| `humidity_pct` | Relative humidity (%) |
| `pm25` | PM2.5 (µg/m³) |

### Refrigeration keys

`app/services/refrigeration_auto_mapper.py` → `REFRIGERATION_LOGICAL_KEYS` (suction pressure, superheat, NH₃ ppm, etc.).

### Storage locations

| Store | Path | Format |
|-------|------|--------|
| Per-building Metasys map | `app/services/metasys_object_store.py` | `logical_key → metasys_object_id` |
| Static demo JSON | `app/data/metasys_objects.json` | Demo object catalog |
| Supabase | `public.building_points` (frontend migrations) | `point_name`, `protocol_address`, metadata JSONB |
| Edge BACnet | `edge/bacnet_points.json` | `logical_key → {device, object}` |
| Refrigeration | `app/data/refrigeration_*_map.json` | Protocol-specific |

### Data origin tagging

`app/services/data_policy.py` → `DataOrigin` enum: `METASYS`, `BACNET`, `MODBUS`, `MQTT`, `IMPORT`, `INFLUX`, `EDGE`, `SIMULATED`, etc.

## Fuzzy Metasys mapping

**Module:** `app/services/metasys_auto_mapper.py`

### Algorithm

1. **Flatten** Metasys tree (`items`, `children`, `objects`, …) → `{id, name, type, label}`.
2. For each logical key, score object labels against regex patterns in `_NAME_RULES`.
3. First-match-wins per key; already-used object IDs excluded.
4. **Merge mode** (`merge=true`): preserve manual overrides in existing map.

### API triggers

```
POST /api/v1/jci/buildings/{building_id}/objects/auto-map?merge=true&force=false
POST /api/v1/jci/auto-connect
```

### Example patterns

| Key | Pattern examples |
|-----|------------------|
| `supply_air_temp` | `\bsat\b`, `supply.?air`, `sa_temp` |
| `total_kw` | `total.*kw`, `main.*meter`, `em.*kw` |
| `co2_ppm` | `\bco2\b`, `carbon.?dioxide` |

### Tests

`tests/test_metasys_auto_mapper.py` — flatten nested payloads, scoring, merge behavior.

## Excel / CSV import

**Module:** `app/services/excel_import.py`

### Supported columns (header aliases)

| Canonical field | Accepted headers |
|-----------------|------------------|
| `point_name` | point name, tag, name |
| `point_type` | type, object type |
| `unit` | unit, engineering unit |
| `protocol_address` | address, bacnet, modbus, object id |
| `zone`, `floor` | zone, floor, level |
| Building meta | name, address, city, `total_area_sqm`, `year_built`, … |

Fuzzy header match: `_match_column()` normalizes whitespace and substring-matches aliases.

### API

Building onboarding upload route (account API) — requires `openpyxl` + `python-multipart` in production image (`requirements-railway.txt` gap).

### Review output

Parser returns `review[]` with fuzzy-match warnings and `unmapped_columns[]` for operator confirmation before activate.

## Frontend mapping UX

| Surface | Path |
|---------|------|
| Tag mapper page | `/tag-mapper` |
| BMS settings | `buildopt-ai/src/pages/BmsSettings.tsx` |
| Logical keys API | `GET /api/v1/jci/logical-keys?domain=hvac` |

## FDD prerequisite linkage

FDD rules declare `requires: [...]` point keys (`app/ml/fault_detector.py`). Unmapped keys → rule status `NOT_EVALUABLE` (see `docs/fdd-rules.md`).

## Building lifecycle

Migration `supabase/migrations/005_building_lifecycle.sql` (mirrored in `buildopt-ai`):

`DRAFT` → `CONFIGURING` → `DISCOVERING` → `MAPPING_REQUIRED` → `VALIDATING` → `ACTIVE`

Point mapping completion should transition `MAPPING_REQUIRED` → `VALIDATING` (enforcement PARTIAL).

## Operator checklist

- [ ] Run `test-connection` successfully
- [ ] Auto-map or import Excel point list
- [ ] Manually verify 4+ critical keys (power, SAT, zone temp, CO₂)
- [ ] Confirm `GET /api/v1/jci/buildings/{id}/objects` matches site nomenclature
- [ ] Poll cycle populates `GET /api/v1/buildings/{id}/live`
