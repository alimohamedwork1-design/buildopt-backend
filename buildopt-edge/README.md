# BuildOpt Edge — Independent, Read-Only Site Gateway

**Important:** This repository contains a gateway framework and **uneven protocol maturity**. It is not a certified, universal connector for every BMS, and deployment does not itself establish a field-validated installation. It does not create an OEM commercial relationship.

## Intended architecture

```text
Customer-authorized OT network and approved endpoints
          │
          ▼
BuildOpt site gateway (explicit read-only scope)
          ├── mapped point inventory + timestamp/quality checks
          ├── encrypted outbound transport to approved BuildOpt API
          └── local SQLite store-and-forward (retention/backup to review)
```

No customer is required to replace its existing controls. No autonomous OT writeback is authorized by this pilot workflow.

## Protocol support — claims boundary

| Adapter pathway | Repository status | Real-site readiness |
|---|---|---|
| BACnet/IP | placeholder interface, not full polling integration | Not field validated |
| Modbus TCP | placeholder interface, not full polling integration | Not field validated |
| MQTT | planned placeholder | Not field validated |
| OPC UA | planned placeholder | Not field validated |
| Approved REST / historian | requires separately validated site-specific adapter | Not field validated |
| Legacy proprietary adapter | isolated optional code, requires lawful licensing and site approvals | Do not claim blanket OEM compatibility |

Legacy edge pathways and the FastAPI main backend are different technical surfaces. Never assume a working Python connector proves this Docker image supports real devices.

## Starting a permissioned pilot

1. Obtain written building-owner OT network permission and a signed pilot scope. Use a dedicated VLAN and least-privilege, read-only user.
2. Review the site adapter's current implementation. **Do not run a placeholder against a production site** and expect telemetry.
3. Issue a scoped `bo_gw_...` gateway token for the right building and tenant through the authorized BuildOpt backend. Do not paste credentials into the public lead form.
4. Configure `GATEWAY_ID`, `TENANT_ID`, `BUILDING_ID`, `GATEWAY_API_KEY`, `CLOUD_API_URL`, `EDGE_CONNECTOR`. The Compose file requires all of them explicitly. Avoid an unreviewed fallback to shared credentials.
5. Review `config/mapped_points.json`, time and units, mapping ownership, site data-retention rules and queue capacity.
6. Use `docker compose config` to inspect the plan, then deploy only after OT engineer acceptance.
7. Verify actual data-source identity, timestamp order, units, quality, loss/reconnect behavior and authorization. Record signed technical evidence before changing connector maturity status.
8. For laboratory work that does not touch a network, run `python -m app.services.integration_lab --protocol bacnet_ip --scenario packet_loss` from the backend root. Results are **synthetic** and not device interoperability certification.

## Resilience and security limitations
- Store-and-forward does not prove durable retention after queue overflow, full disk or host loss. Monitor queue depth, configure backup and define safe data-loss policy with the customer.
- Avoid default passwords, exposed databases and WAN access to OT.
- Review certificate validation, gateway rotation, rollback and observability with the actual customer.
- For an on-prem **reference only** consult `../docs/ONPREM_READ_ONLY_REFERENCE.md`; passing its preflight is **not** site approval.
