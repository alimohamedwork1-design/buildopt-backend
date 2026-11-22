# Decision OS M&V independent holdout review — 2026-11-22

The authenticated existing \`POST /api/v1/decision-os/scenarios/baseline-mv-review\` accepts optional \`validation_periods\` (3–24 periods), independent from the baseline training and reporting period IDs. With these user-supplied records, it computes out-of-sample CVRMSE and NMBE on an OLS cooling-degree-day + operating-hours baseline. The caller can set conservative \`max_holdout_cv_rmse_fraction\` and \`max_abs_holdout_nmbe_fraction\` limits. Exceeding either limit **blocks** the indicative scenario instead of showing a convincing but unfounded energy-savings number.

A successful check still yields \`field_calibrated: false\` and \`holdout_validation.independently_verified: false\`. It cannot verify the meter, measurement boundary, weather station, degree-day base temperature, occupancy, intervention attribution, legal permission, IPMVP compliance or causation. No physical setpoint, equipment command or writeback API is exposed.

Without \`validation_periods\`, existing V2 draft behavior remains backward-compatible; in-sample training CVRMSE is explicitly not independent holdout validation. Customer pilots must use separate source-reviewed data, and signed engineering acceptance cannot be inferred from this API.
