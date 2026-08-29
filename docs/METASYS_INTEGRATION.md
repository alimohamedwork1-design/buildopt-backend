# Metasys Integration (Production)

Primary BMS: Johnson Controls Metasys REST v4/v5  
Pilot phase: READ ONLY

---

## Connector

`app/services/bms_connector.py` — MetasysConnector  
HTTP: `app/services/jci_metasys.py`

Write disabled: returns `write_disabled_pilot_read_only`

---

## API routes

POST /jci/test-connection, /save-credentials, /network-diagnostic  
GET/PUT /jci/buildings/{id}/objects  
POST /jci/buildings/{id}/objects/auto-map  
GET /jci/objects/{id}/present-value

---

## Security

Credentials encrypted in Supabase. Never logged. Never returned to browser.

---

## Real integration test

BLOCKED until pilot Metasys credentials (B1)

See also: `docs/metasys-integration.md` (Phase 0 audit)
