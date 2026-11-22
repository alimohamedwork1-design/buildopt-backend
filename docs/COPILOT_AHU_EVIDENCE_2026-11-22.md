# BuildOpt Engineering Copilot — AHU temperature evidence review

Authorized \`POST /api/v1/engineering-copilot/investigate\` now supports \`equipment_type: "air_handling_unit"\` with good-quality, recent, <=2-minute-apart \`ahu_supply_c\` and \`ahu_return_c\` values in °C.

The response reports a bounded supply/return air delta. To emit an illustrative **review** flag, a caller must explicitly declare \`declared_operating_mode: "cooling"\` and a site-specified \`operator_min_cooling_delta_c\` between 0.5°C and 20°C. If the operating mode or threshold is absent, the endpoint merely describes the observed difference; it does not label a fault. Stale, impossible, misaligned or incorrectly typed measurements are blocked.

This cannot identify a bad coil, valve, damper, airflow or sensor without corroborating site evidence. It never causes a write to Metasys, a BACnet controller or a PLC; all recommendations require an engineer. A mocked API payload does not prove measured site data, root cause, or energy savings. See \`tests/test_evidence_copilot.py\`.
