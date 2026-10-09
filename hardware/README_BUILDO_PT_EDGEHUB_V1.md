# BuildOpt Edge Hub V1 — One custom-manufactured CM4 device

**Engineering disposition: CONDITIONAL / NOT released to fabrication.**

## What is in this GitHub branch

- **Real KiCad reference CAD**: `hardware/reference/cm4-carrier-net/` (legacy KiCad .sch, routed four-layer .kicad_pcb, library tables, author BSD-2-Clause license). Source: https://github.com/jkiv/cm4-carriers at main, fetched for design reuse with copyright notice preserved.
- Production-oriented Modbus/TCP + Modbus/RTU read-only connector under `buildopt-edge/app/connectors/modbus.py`; site authorization opt-in required for non-loopback physical devices.
- Three operating modes parsed by the Linux agent: `EDGE_OPERATING_MODE=offline|hybrid|hybrid_4g`. In offline mode no cloud API calls are made. `hybrid_4g` **does not** configure modem hardware; a separately configured router/OS must provide cellular WAN failover.
- Cloud retry/partial ACK safeguards; SQLite outbox never trims away unacknowledged rows merely due to configured row limit. Real disk-full resilience **still needs site test and monitoring**.
- Contract tests in `tests/test_edgehub_v1_*.py`. These are software tests; never use them as EMC or electrical acceptance proof.

## Route to the first *working* unit with minimum custom engineering spend

**Variant A — one-off self-assembled functional product:**
1. Have one PCB of the **referenced open-source CM4 carrier** assembled by a qualified PCBA supplier only **after its version-specific schematic, BOM, USB OTG / host mode, Ethernet, power and KiCad ERC/DRC have been independently reviewed**. Keep BSD-2 attribution in sold products. The reference PCB is NOT a BuildOpt-custom integrated RS485 board.
2. Plug an official Raspberry Pi CM4 **CM4002016** (2GB, 16GB eMMC, no wireless) into the correctly matched CM4 connectors and 5 V power from a properly protected **24 VDC → 5 V 6 A** approved DIN converter, e.g. Mean Well **DDR-30G-5**. Validate converter input range, lead sizes, fusing, ambient derating, temperature and the carrier's USB-C current carrying path before power-up.
3. Start with **Modbus TCP**, through a permitted industrial LAN and site firewall. For RS485/RTU only use a separately verified **isolated USB/RS485 interface**, after confirming CM4 USB host mode and chipset Linux kernel driver on this specific carrier; do not assume a USB-C data connector is automatically a host.
4. Install Linux image, supervised BuildOpt agent, read-only tag map, authorized gateway token, strict OT firewall rules, local SQLite queue, monitoring, watchdog, and the selected operating mode.
5. Add an **external 4G router + antenna + SIM** only after functional wired WAN testing. Keep no uncontrolled remote ingress to OT.

**Variant B — fully integrated BuildOpt-designed single PCB:** The staged upstream carrier files are a routing reference, not final BuildOpt schematics. Draw and review a new RS485 isolation + power + USB/CM4 schematic, route PCB, close ERC/DRC, and verify first article before manufacturing. **Do not request Gerbers from this branch as a completed product board.**

## Hold points (mandatory before any order)

- Correct CM4 200-pin mapping, mating connector stack height, DDR routing unaffected, Ethernet magnetics / shield ground, boot/emmc programming, USB mode and thermal enclosure.
- Read verified source manufacturer datasheets and confirm every MPN, footprint, and stock.
- 24 VDC isolation and transient testing; **NO AC MAINS** inside custom PCB.
- Physical creepage/clearance and surge tests on RS485; do not short isolated field ground to logic ground.
- KiCad 8+ import/re-export and **zero unresolved ERC/DRC**, CAM validation, IPC assembly tolerances.
- No physical unit has been assembled or accepted; physical BOM pricing not fixed.

## References

- Raspberry Pi original KiCad: https://pip.raspberrypi.com/categories/1210-design-files
- CM4 datasheet: https://pip-assets.raspberrypi.com/categories/634-raspberry-pi-compute-module-4/documents/RP-008168-DS/cm4-datasheet
- Upstream carrier + license: https://github.com/jkiv/cm4-carriers
- Mean Well DDR-30G-5: https://www.meanwell.com/Upload/PDF/DDR-30/DDR-30-spec.pdf
- Waveshare isolated USB/RS485: https://docs.waveshare.com/USB_TO_RS485_C/User-Guide
