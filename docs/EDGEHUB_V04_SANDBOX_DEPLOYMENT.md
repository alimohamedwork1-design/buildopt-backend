# BuildOpt Edge Hub Mini V0.4 — Sandbox Cloud Integration

> **Status:** Code changes on feature branch. No production credentials are stored here. No live building may receive simulator data.

## Components

- **Simulator (user ZIP):** Python Virtual Modbus TCP PLC, local dashboard, SQLite queue, 3 offline/hybrid/4G *simulation* modes.
- **Backend:** Existing `/api/v1/discovery/points/batch`, `/api/v1/telemetry/batch`, `/api/v1/gateways/heartbeat` and new `/api/v1/gateways/{id}/provision`.
- **Frontend:** Existing `/edge-fleet` view consumes authenticated `/api/v1/gateways` — do not include master ingest key in JavaScript.

## Prerequisites for real E2E (not yet performed)

1. Merge and deploy backend PR and frontend PR together to a **test** environment.
2. Configure backend `APP_ENV=production`, nonempty `INGEST_API_KEY`, secure `SECRET_KEY`, and a durable telemetry store.
3. Ensure that the `tenant_id` and `building_id` identify an already-authorized **nonoperational sandbox building**. This API does **not** create or validate an account-owned building.
4. On an admin machine, set `BUILDOPT_ADMIN_INGEST_KEY` in the environment (never on the Edge):
   `python provision.py --cloud-url https://YOUR-BACKEND --gateway-id sim-edge-lab-001 --building-id SANDBOX_BUILDING --tenant-id SANDBOX_TENANT --confirm-test-building`.
   The tool stores only a short-lived **scoped** token in ignored `.env.edge`.
5. On the Edge test machine run `python run_connected.py`. No real PLC is accessed.
6. Verify discovery acknowledges all points, telemetry response `accepted`, and Gateway heartbeat is visible for the permitted logged-in account.
7. Interrupt WAN; confirm queue growth and local alarm/FDD; restore network and confirm queue drained without duplicated IDs; switch Offline mode and confirm no new WAN requests.
8. Confirm **simulated** markers survive telemetry ingestion, and are never included in production control, savings verification, or live-building reporting.

## Security invariants

- Live cloud requires HTTPS, `bo_gw_*` token and explicit demo upload opt-in.
- Provisioning requires configured master key even in development.
- Gateway provisioning binds gateway ID to building ID + tenant ID + connector ID before minting token, rejects scope changes, and requires `sim-*` identifier plus test-building confirmation.
- Fleet list returns only authorized building gateways (or admin / verified master service).
- Master key MUST NOT be on edge host or shipped to browser.
- Cloud cannot control local outputs from Edge Fleet. Outputs stay disabled by default.
- 4G mode relies on external router/OS WAN failover in physical deployments. A second localhost endpoint represents *simulated* cellular path in tests.
- Heartbeats are stored **in memory** by the current backend: disappearing across backend restart is expected. Production fleet history requires a durable heartbeat store in future work.
- Scoped tokens are currently only gateway-ID scoped in `verify_ingest_key`; the registered scope is enforced by `authorize_gateway`. Do not bypass either step.
- The existing backend may accept `simulated=true` tags as telemetry. Operators must explicitly avoid mixing test data with live buildings.

## Test commands

Backend:
```bash
pytest tests/test_edgehub_provision.py tests/test_phase3_telemetry.py -q
```
Edge package:
```bash
python -m unittest discover -s tests -v
python smoke_modes.py
```

## Rollback

Disable the Edge process; revoke its token using the admin endpoint; revert the feature branch/PR deployment. Do **not** delete the local queue or lose forensic events. Back up its SQLite database before wiping the sandbox registry. No production control state changes are part of this rollout.
