"""Engineering acceptance helpers for BuildOpt ten-stream delivery.

All inputs are caller-supplied. These functions can *reject* implausible or
noncomparable assumptions, but CANNOT independently verify a building, consent,
measured savings, a payment, a calibration certificate or a safety case.
No BMS connector, writeback, file system or network side effects.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from math import sqrt
from typing import Literal

from pydantic import Field, model_validator
from app.services.decision_engine import StrictModel, SourceMode, _common


class BenchmarkSite(StrictModel):
    building_id: str = Field(min_length=1, max_length=128)
    meter_reference: str = Field(min_length=9, max_length=160)
    category: str = Field(min_length=3, max_length=100)
    climate_zone: str = Field(min_length=2, max_length=100)
    meter_boundary: str = Field(min_length=5, max_length=200)
    period_start: date
    period_end: date
    energy_kwh: float = Field(gt=0, le=100_000_000)
    floor_area_m2: float = Field(gt=0, le=10_000_000)
    coverage_fraction: float = Field(ge=0, le=1)
    cooling_degree_days: float = Field(gt=0, le=10000)
    occupied_hours: float = Field(gt=0, le=10000)
    permission_declared: bool = False


class PortfolioReviewRequest(StrictModel):
    building_id: str = Field(min_length=1, max_length=128)
    sites: list[BenchmarkSite] = Field(min_length=2, max_length=15)
    source_mode: SourceMode
    read_only: Literal[True] = True

    @model_validator(mode="after")
    def identities(self):
        ids = [x.building_id for x in self.sites]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate building identities")
        if self.building_id not in ids:
            raise ValueError("The authorized request building must be in the site list")
        return self


def review_portfolio(p: PortfolioReviewRequest) -> dict:
    base = _common(p.source_mode,p.building_id,"portfolio_comparability")
    blockers = []
    rows = p.sites
    b0 = rows[0]
    for x in rows:
        duration = (x.period_end-x.period_start).days
        if duration < 330 or duration > 400:
            blockers.append("nonannual_period:" + x.building_id)
        if x.coverage_fraction < .95:
            blockers.append("coverage_below_95_percent:" + x.building_id)
        if not x.permission_declared:
            blockers.append("site_permission_not_declared:" + x.building_id)
        if x.category.strip().lower() != b0.category.strip().lower():
            blockers.append("building_use_not_comparable:" + x.building_id)
        if x.climate_zone.strip().lower() != b0.climate_zone.strip().lower():
            blockers.append("climate_zone_not_comparable:" + x.building_id)
        if x.meter_boundary.strip().lower() != b0.meter_boundary.strip().lower():
            blockers.append("meter_boundary_not_comparable:" + x.building_id)
        if abs((x.period_start-b0.period_start).days)>7 or abs((x.period_end-b0.period_end).days)>7:
            blockers.append("period_dates_do_not_align:" + x.building_id)
        if abs(x.cooling_degree_days/b0.cooling_degree_days-1)>.1:
            blockers.append("weather_not_comparable:" + x.building_id)
        if abs(x.occupied_hours/b0.occupied_hours-1)>.1:
            blockers.append("occupancy_hours_not_comparable:" + x.building_id)
    # We do not "normalize" kWh with an invented coefficient; without validated
    # site-specific models, it would falsely imply weather-adjusted accuracy.
    comparable = not blockers
    result = [] if not comparable else [{
        "building_id":x.building_id,
        "raw_annualized_eui_kwh_m2":round(x.energy_kwh*365.25/(x.period_end-x.period_start).days/x.floor_area_m2,3),
        "coverage_fraction":x.coverage_fraction,"meter_reference":x.meter_reference,
    } for x in rows]
    return {**base,"comparable_for_engineering_review":comparable,
        "blockers":blockers,"results":result,
        "external_peer_percentile":None,"carbon_savings_verified":False,
        "assumptions":[
          "All meters, floor areas, weather, occupancy, site permissions and boundaries are operator-declared.",
          "Only near-equivalent conditions are compared. Values are RAW annualized EUI, not adjusted weather-normalized EUI.",
          "No external peer rating, causal inference, meter-source verification or verified savings.",
        ]}


class TwinHoldoutPoint(StrictModel):
    sample_id: str = Field(min_length=3, max_length=100)
    source_reference: str = Field(min_length=9, max_length=160)
    observed_kwh: float = Field(ge=0, le=10_000_000)
    predicted_kwh: float = Field(ge=0, le=10_000_000)
    observed_at: datetime

    @model_validator(mode="after")
    def valid_observation(self):
        if self.observed_at.tzinfo is None:
            raise ValueError("Holdout timestamp must have timezone")
        return self


class TwinCalibrationRequest(StrictModel):
    building_id: str = Field(min_length=1, max_length=128)
    model_reference: str = Field(min_length=9, max_length=160)
    holdout_points: list[TwinHoldoutPoint] = Field(min_length=12, max_length=500)
    max_cv_rmse_fraction: float = Field(default=.15, gt=0, le=.5)
    max_abs_nmbe_fraction: float = Field(default=.05, gt=0, le=.5)
    points_are_independent_holdout: bool = False
    source_mode: SourceMode
    read_only: Literal[True] = True

    @model_validator(mode="after")
    def unique_samples(self):
        ids=[row.sample_id for row in self.holdout_points]
        if len(ids)!=len(set(ids)):
            raise ValueError("Duplicate holdout sample")
        return self


def review_twin_calibration(p:TwinCalibrationRequest)->dict:
    base=_common(p.source_mode,p.building_id,"twin_holdout_calibration_review")
    blockers=[]
    if not p.points_are_independent_holdout:
        blockers.append("holdout_independence_not_declared")
    actual=[x.observed_kwh for x in p.holdout_points]
    pred=[x.predicted_kwh for x in p.holdout_points]
    mean=sum(actual)/len(actual)
    if mean<=0:
        blockers.append("zero_mean_observed_energy")
        return {**base,"blockers":blockers,"review_candidate":False,"metrics":None,
                "model_calibrated":False,"field_validated":False}
    rmse=sqrt(sum((a-b)**2 for a,b in zip(actual,pred))/len(actual))
    cv=rmse/mean
    nmbe=sum(a-b for a,b in zip(actual,pred))/(len(actual)*mean)
    if cv>p.max_cv_rmse_fraction:
        blockers.append("holdout_cv_rmse_above_declared_threshold")
    if abs(nmbe)>p.max_abs_nmbe_fraction:
        blockers.append("holdout_nmbe_above_declared_threshold")
    return {**base,"blockers":blockers,"review_candidate":not blockers,
        "metrics":{"holdout_cv_rmse_fraction":round(cv,5),
            "holdout_nmbe_fraction":round(nmbe,5),"holdout_sample_count":len(actual)},
        "model_reference":p.model_reference,"model_calibrated":False,
        "assumptions":[
          "Holdout independence and source references are unverified operator assertions.",
          "Passing numerical thresholds is only readiness for independent engineering review, NOT site model calibration.",
          "No physics constraints, control output, field certification, performance guarantee or verified savings.",
        ]}


class OnPremPreflightRequest(StrictModel):
    building_id: str = Field(min_length=1,max_length=128)
    private_network_isolated: bool = False
    tls_certificate_validated: bool = False
    sso_tested: bool = False
    secrets_in_managed_store: bool = False
    role_scopes_tested: bool = False
    backup_encrypted: bool = False
    restore_drill_passed: bool = False
    upgrade_rollback_tested: bool = False
    log_redaction_tested: bool = False
    incident_owner_assigned: bool = False
    read_only_gateway_enabled: bool = False
    source_mode: SourceMode
    read_only: Literal[True] = True


def review_onprem(p:OnPremPreflightRequest)->dict:
    checks={
      "private_network_isolated":p.private_network_isolated,
      "tls_certificate_validated":p.tls_certificate_validated,
      "sso_tested":p.sso_tested,
      "secrets_in_managed_store":p.secrets_in_managed_store,
      "role_scopes_tested":p.role_scopes_tested,
      "backup_encrypted":p.backup_encrypted,
      "restore_drill_passed":p.restore_drill_passed,
      "upgrade_rollback_tested":p.upgrade_rollback_tested,
      "log_redaction_tested":p.log_redaction_tested,
      "incident_owner_assigned":p.incident_owner_assigned,
      "read_only_gateway_enabled":p.read_only_gateway_enabled,
    }
    missing=[k for k,v in checks.items() if not v]
    return {**_common(p.source_mode,p.building_id,"onprem_preflight"),
      "declared_checks_count":sum(checks.values()),
      "total_checks":len(checks),"missing_declarations":missing,
      "ready_for_independent_security_validation":not missing,
      "production_certified":False,
      "note":"Self-declared checklist, not an infrastructure scan or penetration test; keep BMS writes disabled."}
