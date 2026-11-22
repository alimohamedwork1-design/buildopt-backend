# Engineering delivery review API
Three **strictly read-only**, authenticated APIs now support BuildOpt's ten-stream delivery acceptance workflow. The endpoints never query physical OT, send equipment commands or claim verified savings.

- POST /api/v1/delivery-review/portfolio: require the requestor to be assigned to **every** supplied building (not just the first). Require comparable declared metering boundaries, same use/climate zone, 330–400 day windows, >=95% data coverage, +/-7-day date alignment, +/-10% degree days and occupancy hours. Returns only raw annualized EUI. Does not compute weather-normalized EUI or external peer rank.
- POST /api/v1/delivery-review/twin-calibration: 12–500 time-zoned user-supplied independent holdout samples; compute CVRMSE and NMBE and compare to declared thresholds. Even an in-range model remains uncalibrated until an actual engineer checks references and operating constraints.
- POST /api/v1/delivery-review/onprem: 11 operator-declared security conditions including isolated network, TLS, SSO, secret store, scopes, encrypted backups, restore drill, rollback, redacted logs, incident owner, read-only gateway. No real host check occurs.

Copilot hardening: reject NaN/Infinity, timezone-free source timestamps, future received/processed timestamps and >2 minute CHW sample skew. An unaligned delta-T must be marked insufficient evidence, not a diagnosis.

CI: \`tests/test_engineering_acceptance.py\` and \`tests/test_evidence_copilot.py\`. Auth checks require building assignment, and portfolio endpoint checks all listed building identities individually. Tests are synthetic fixtures only.

No actual site, security certification, paid pilot or controls writeback is implied.
