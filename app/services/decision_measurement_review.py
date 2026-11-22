"""Read-only M&V *review preparation* using operator-provided energy periods.

Ordinary least squares with cooling degree days + operating hours. No IPMVP
certification, calibrated physical model, utility data retrieval or VERIFIED state.
The chosen meter boundary, baseline and weather inputs are submitted by the
caller and are NOT independently authenticated by this service.
"""
from __future__ import annotations

from math import sqrt
from typing import Literal

from pydantic import Field, model_validator

from app.services.decision_engine import StrictModel, SourceMode, _common


class MeterPeriod(StrictModel):
    period_id: str = Field(min_length=3, max_length=64)
    meter_reference: str = Field(min_length=5, max_length=128)
    energy_kwh: float = Field(ge=0, le=10_000_000)
    cooling_degree_days: float = Field(ge=0, le=5000)
    operating_hours: float = Field(ge=0, le=744)
    coverage_fraction: float = Field(ge=0, le=1)


class MeasurementReviewRequest(StrictModel):
    building_id: str = Field(min_length=1, max_length=128)
    measurement_boundary: str = Field(min_length=8, max_length=300)
    baseline_periods: list[MeterPeriod] = Field(min_length=12, max_length=48)
    reporting_periods: list[MeterPeriod] = Field(min_length=1, max_length=24)
    min_reporting_coverage: float = Field(default=0.9, ge=0.8, le=1.0)
    max_training_cv_rmse: float = Field(default=0.25, gt=0, le=0.50)
    source_mode: SourceMode
    read_only: Literal[True] = True

    @model_validator(mode="after")
    def unique_periods(self):
        ids=[p.period_id for p in self.baseline_periods + self.reporting_periods]
        if len(ids)!=len(set(ids)):
            raise ValueError("Baseline and reporting period IDs must be distinct")
        return self


def _least_squares_three(rows: list[tuple[float,float,float,float]]) -> tuple[float,float,float] | None:
    # Three predictors: intercept, cooling degree days, operating hours.
    # Solve normal equations with partial pivoting and strict rank guard.
    a=[[0.0]*4 for _ in range(3)]
    for x,y,z,energy in rows:
        q=(x,y,z)
        for i in range(3):
            a[i][3]+=q[i]*energy
            for j in range(3):
                a[i][j]+=q[i]*q[j]
    for i in range(3):
        pivot=max(range(i,3),key=lambda k:abs(a[k][i]))
        col_scale=max(abs(a[k][i]) for k in range(i,3))
        if col_scale < 1e-10:
            return None
        if pivot != i:
            a[i],a[pivot]=a[pivot],a[i]
        div=a[i][i]
        for j in range(i,4):
            a[i][j]/=div
        for k in range(3):
            if k==i:continue
            factor=a[k][i]
            for j in range(i,4):
                a[k][j]-=factor*a[i][j]
    return (a[0][3],a[1][3],a[2][3])


def prepare_mv_review(p: MeasurementReviewRequest) -> dict:
    base=_common(p.source_mode,p.building_id,"baseline_mv_review")
    assumptions=[
        "Simple in-sample least-squares energy baseline using operator-supplied CDD and operating hours.",
        "Cooling degree day base temperature, weather station and metering boundary are not independently audited.",
        "CVRMSE shown is in-sample fit error, not an independently held-out model or a calibrated uncertainty interval.",
        "A positive difference is NOT energy savings verification or an IPMVP-certified result.",
        "Meter references and coverage are declared by the operator; signed independent engineering review remains mandatory.",
    ]
    incomplete=[t.period_id for t in p.baseline_periods+p.reporting_periods
                if t.coverage_fraction < p.min_reporting_coverage]
    if incomplete:
        return {**base,"feasible":False,"blockers":["inadequate_meter_coverage"],
                "affected_periods":incomplete,"best":None,
                "assumptions":assumptions,"measurement_boundary":p.measurement_boundary}
    if not any(row.energy_kwh>0 for row in p.baseline_periods):
        return {**base,"feasible":False,"blockers":["baseline_energy_zero"],
                "best":None,"assumptions":assumptions,"measurement_boundary":p.measurement_boundary}
    design=[(1.0,row.cooling_degree_days,row.operating_hours,row.energy_kwh)
            for row in p.baseline_periods]
    coeff=_least_squares_three(design)
    if coeff is None:
        return {**base,"feasible":False,"blockers":["collinear_or_insufficient_baseline_variation"],
                "best":None,"assumptions":assumptions,"measurement_boundary":p.measurement_boundary}
    def predict(row: MeterPeriod) -> float:
        return coeff[0]+coeff[1]*row.cooling_degree_days+coeff[2]*row.operating_hours
    baseline_preds=[predict(row) for row in p.baseline_periods]
    reporting_preds=[predict(row) for row in p.reporting_periods]
    if any(value<0 for value in baseline_preds+reporting_preds):
        return {**base,"feasible":False,"blockers":["nonphysical_negative_predicted_energy"],
                "best":None,"assumptions":assumptions,"measurement_boundary":p.measurement_boundary}
    error=sqrt(sum((row.energy_kwh-yhat)**2 for row,yhat in zip(p.baseline_periods,baseline_preds))
               / len(p.baseline_periods))
    average=sum(row.energy_kwh for row in p.baseline_periods)/len(p.baseline_periods)
    cv_rmse=error/average if average>0 else 999
    if cv_rmse>p.max_training_cv_rmse:
        return {
            **base,"feasible":False,"blockers":["baseline_fit_exceeds_review_threshold"],
            "training_cv_rmse_fraction":round(cv_rmse,4),"best":None,
            "assumptions":assumptions,"measurement_boundary":p.measurement_boundary,
        }
    adjusted=sum(reporting_preds)
    measured=sum(row.energy_kwh for row in p.reporting_periods)
    return {
        **base,"feasible":True,"blockers":[],
        "measurement_boundary":p.measurement_boundary,
        "measurement_status":"OPERATOR_OBSERVED_NOT_INDEPENDENTLY_VERIFIED",
        "verification_status":"READY_FOR_INDEPENDENT_ENGINEERING_REVIEW_ONLY",
        "baseline_model":{
            "method":"OLS_CDD_AND_OPERATING_HOURS",
            "coefficients":{"intercept":round(coeff[0],5),
                            "cdd_kwh_per_unit":round(coeff[1],5),
                            "operating_hours_kwh_per_hour":round(coeff[2],5)},
            "training_cv_rmse_fraction":round(cv_rmse,4),
            "baseline_period_count":len(p.baseline_periods),
            "reporting_period_count":len(p.reporting_periods),
            "source_refs":[row.meter_reference for row in p.baseline_periods+p.reporting_periods],
        },
        "best":{
            "modeled_adjusted_baseline_kwh":round(adjusted,3),
            "operator_reported_actual_kwh":round(measured,3),
            "indicative_adjusted_difference_kwh":round(adjusted-measured,3),
            "indicative_difference_pct":round(100*(adjusted-measured)/adjusted,3) if adjusted>0 else None,
            "reporting_periods":[{"period_id":row.period_id,
                "modeled_adjusted_baseline_kwh":round(pred,3),
                "operator_reported_energy_kwh":round(row.energy_kwh,3),
                "coverage_fraction":row.coverage_fraction}
                for row,pred in zip(p.reporting_periods,reporting_preds)],
        },
        "assumptions":assumptions,
    }
