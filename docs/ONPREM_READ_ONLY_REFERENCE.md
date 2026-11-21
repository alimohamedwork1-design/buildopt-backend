# BuildOpt AI — On-Premise / Private Customer Deployment Reference (NOT PRODUCTION CERTIFIED)

**Status (21 November 2026):** reference configuration and automated policy preflight. This document does **not** prove a deployable enterprise SKU. The main web portal, auth stack, backend, gateway and DB need customer-specific integration and end-to-end review.

## Minimum equipment / network design

```text
Approved BMS/plant LAN (customer-owned)
      └── dedicated outbound-only OT VLAN, site network owner
              └── Approved, validated BuildOpt edge adapter
                    ├── bounded read-only access
                    ├── local queue + health/quality metadata
                    └── egress HTTPS/mTLS as approved
                          │
                          ▼
Private BuildOpt application network
  ├── API (localhost or private reverse proxy; not public OT-facing)
  ├── Database / historian (private only; backups + integrity checks)
  ├── identity provider & customer tenant mapping (requires configuration)
  └── UI behind customer-reviewed TLS reverse proxy and WAF
```

**No writeback** and no arbitrary inbound connection from the public Internet to an OT controller. No default OEM dependency, vendor logo or blanket compatibility claim.

## Required security preflight

Before running anything on a customer site, create a site-specific environment using an approved secret manager. Never commit the real `.env` file. These values must not be left empty/default:

```bash
# Illustration only — use secret manager, no real secrets in examples.
APP_ENV=production
DEMO_MODE=false
SECRET_KEY=<generate-a-random-minimum-32-character-secret>
INFLUX_ADMIN_USER=<approved-admin-account>
INFLUX_ADMIN_PASSWORD=<strong-random-password>
INFLUX_TOKEN=<strong-random-private-token>
ALLOWED_ORIGINS=https://<reviewed-customer-domain>
CONTROL_WRITEBACK_ENABLED=false
OT_NETWORK_APPROVED=false
TLS_REVERSE_PROXY_VERIFIED=false
OFFSITE_BACKUP_RESTORE_VERIFIED=false
CUSTOMER_SOW_SIGNED=false
```

Preflight:

```bash
python scripts/onprem_preflight.py --format json
docker compose -f docker-compose.yml config -q
```

The Python preflight returns exit code 2 for missing/unsafe basic config. Passing preflight is **necessary but not sufficient**: it does not verify real encrypted communication, entitlement, licenses, keys on server or the production database. Manual OT/legal conditions must be separately accepted and recorded.

The root `docker-compose.yml` is a **development reference** running a local FastAPI service plus private InfluxDB. It binds port 8000 to 127.0.0.1 and contains **no hardcoded DB credentials**. It does not provision a frontend, SSO, reverse proxy, email or Supabase; those dependencies must be implemented with the customer's IT department before an enterprise production offer.

## Customer acceptance list

- [ ] legal DPA and signed customer site permission / scope and data retention
- [ ] licensed/authorized adapter and no manufacturer-IP violations
- [ ] network separation, outbound-only allowlist, no open BMS WAN ports
- [ ] deploy all application dependencies with restricted public entry and TLS
- [ ] authenticated tenant isolation, staff and partner least-privilege tests
- [ ] observed **actual** telemetry with source IDs, units and all three timestamps
- [ ] quality gates, disconnect/reconnect, queue overflow and server-side idempotency tested
- [ ] backup/restore drill, time synchronization and network failure drills
- [ ] explicit read-only operations and physical safety owner sign-off
- [ ] field evidence report and customer engineer acceptance
- [ ] operational patch schedule, rollback, incident SLA and point of contact
- [ ] no artificial savings or AI-accuracy claim in accepted report

## Known product gaps

The protocol placeholders in `buildopt-edge/app/connectors` (for BACnet/IP, Modbus, MQTT and OPC UA) are **not field drivers**. Separate backend client code or a lab fixture does not cure that gap. Physical testing and support engineering are required.

The actual production database and secure cloud lead intake remain subject to external Supabase/Cloudflare credentials and account rights. Code merges do not apply live database migrations.

**Decision rule:** do not market On-Prem as production available until a complete isolated deployment, backup restore, authentication and vendor-neutral field acceptance passes.
