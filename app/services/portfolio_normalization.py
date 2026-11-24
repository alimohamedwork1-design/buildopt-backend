"""Bounded, source-declared cross-site normalization. Not a calibrated/verified rating."""
from __future__ import annotations
from datetime import date
from math import isfinite, sqrt
from typing import Literal
from pydantic import Field, model_validator
from app.services.decision_engine import StrictModel, SourceMode, _common
from app.services.decision_measurement_review import _least_squares_three

class MonthlyConditions(StrictModel):
    month: date
    cooling_degree_days: float = Field(ge=0, le=2000)
    occupied_hours: float = Field(ge=0, le=744)

    @model_validator(mode="after")
    def calendar_month(self):
        if self.month.day != 1:
            raise ValueError("Month must be the first day of a calendar month")
        import calendar
        if self.occupied_hours > calendar.monthrange(self.month.year,self.month.month)[1]*24:
            raise ValueError("Occupied hours exceed hours in calendar month")
        return self

class MonthlyMeter(MonthlyConditions):
    energy_kwh: float = Field(ge=0, le=100_000_000)
    coverage_fraction: float = Field(ge=0, le=1)
    source_ref: str = Field(min_length=9, max_length=160)

class SiteNormalizationModel(StrictModel):
    building_id: str = Field(min_length=1,max_length=128)
    category: str = Field(min_length=3,max_length=100)
    meter_boundary: str = Field(min_length=5,max_length=200)
    floor_area_m2: float = Field(gt=0,le=10_000_000)
    permission_declared: bool = False
    weather_reference: str = Field(min_length=9,max_length=160)
    occupancy_definition: str = Field(min_length=5,max_length=200)
    cdd_base_c: float = Field(ge=0,le=35)
    training_months: list[MonthlyMeter] = Field(min_length=12,max_length=36)
    holdout_months: list[MonthlyMeter] = Field(min_length=3,max_length=12)

    @model_validator(mode="after")
    def distinct_months(self):
        months=[x.month for x in self.training_months+self.holdout_months]
        if len(months)!=len(set(months)):
            raise ValueError("Training and holdout calendar months must be distinct")
        if max(x.month for x in self.training_months)>=min(x.month for x in self.holdout_months):
            raise ValueError("Holdout months must follow the training interval")
        return self

class NormalizedPortfolioRequest(StrictModel):
    building_id: str = Field(min_length=1,max_length=128)
    sites: list[SiteNormalizationModel] = Field(min_length=2,max_length=10)
    reference_months: list[MonthlyConditions] = Field(min_length=12,max_length=12)
    reference_label: str = Field(min_length=9,max_length=160)
    max_training_cv_rmse: float = Field(default=.25,gt=0,le=.5)
    max_holdout_cv_rmse: float = Field(default=.30,gt=0,le=.5)
    max_abs_holdout_nmbe: float = Field(default=.10,gt=0,le=.3)
    source_mode: SourceMode
    read_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_scope(self):
        ids=[x.building_id for x in self.sites]
        if len(ids)!=len(set(ids)) or self.building_id not in ids:
            raise ValueError("Each site must be unique and include request building")
        months=sorted(x.month.year*12+x.month.month for x in self.reference_months)
        if months!=list(range(months[0],months[0]+12)):
            raise ValueError("Reference must span 12 consecutive calendar months")
        return self

def review_normalized_portfolio(p:NormalizedPortfolioRequest)->dict:
    base=_common(p.source_mode,p.building_id,"portfolio_model_normalization")
    blockers=[]
    diagnostics=[]
    results=[]
    first=p.sites[0]
    for site in p.sites:
        local=[]
        if not site.permission_declared: local.append("permission_not_declared")
        if site.category.casefold()!=first.category.casefold():local.append("building_category_mismatch")
        if site.meter_boundary.casefold()!=first.meter_boundary.casefold():local.append("meter_boundary_mismatch")
        if site.occupancy_definition.casefold()!=first.occupancy_definition.casefold():local.append("occupancy_definition_mismatch")
        if abs(site.cdd_base_c-first.cdd_base_c)>1e-6:local.append("cdd_base_temperature_mismatch")
        t=site.training_months
        h=site.holdout_months
        if any(x.coverage_fraction<.95 for x in t+h):local.append("coverage_below_95_percent")
        # No extrapolation in either marginal predictor range. This is not a joint
        # convex-hull or confidence-interval claim; full site review is still required.
        cdd=[x.cooling_degree_days for x in t]; hours=[x.occupied_hours for x in t]
        if any(not(min(cdd)<=x.cooling_degree_days<=max(cdd) and min(hours)<=x.occupied_hours<=max(hours))
               for x in p.reference_months+h):
            local.append("conditions_outside_training_range")
        coeff=_least_squares_three([(1.0,x.cooling_degree_days,x.occupied_hours,x.energy_kwh) for x in t])
        if coeff is None or any(not isfinite(x) for x in coeff):
            local.append("insufficient_independent_training_variation")
        metrics=None
        predictions=[]
        if coeff is not None and all(isfinite(x) for x in coeff):
            predict=lambda x:coeff[0]+coeff[1]*x.cooling_degree_days+coeff[2]*x.occupied_hours
            predictions=[predict(x) for x in p.reference_months]
            training=[predict(x) for x in t]; held=[predict(x) for x in h]
            if any(not isfinite(x) or x<0 for x in predictions+training+held):
                local.append("nonphysical_prediction")
            else:
                train_mean=sum(x.energy_kwh for x in t)/len(t)
                hold_mean=sum(x.energy_kwh for x in h)/len(h)
                if min(train_mean,hold_mean)<=0:local.append("zero_mean_observed_energy")
                else:
                    train_cv=sqrt(sum((x.energy_kwh-y)**2 for x,y in zip(t,training))/len(t))/train_mean
                    hold_cv=sqrt(sum((x.energy_kwh-y)**2 for x,y in zip(h,held))/len(h))/hold_mean
                    bias=sum(x.energy_kwh-y for x,y in zip(h,held))/(hold_mean*len(h))
                    metrics={"training_cv_rmse":round(train_cv,5),"holdout_cv_rmse":round(hold_cv,5),
                      "holdout_nmbe":round(bias,5),"training_month_count":len(t),"holdout_month_count":len(h)}
                    if train_cv>p.max_training_cv_rmse:local.append("training_fit_failed")
                    if hold_cv>p.max_holdout_cv_rmse:local.append("holdout_fit_failed")
                    if abs(bias)>p.max_abs_holdout_nmbe:local.append("holdout_bias_failed")
        diagnostics.append({"building_id":site.building_id,"metrics":metrics,"blockers":local,
                            "meter_source_refs":[x.source_ref for x in t+h],"weather_reference":site.weather_reference})
        if local:
            blockers.extend(site.building_id+":"+b for b in local)
        elif metrics is not None:
            modeled=sum(predictions)
            results.append({"building_id":site.building_id,"model_normalized_annual_kwh":round(modeled,3),
              "model_normalized_eui_kwh_m2":round(modeled/site.floor_area_m2,3),
              "floor_area_m2":site.floor_area_m2,"minimum_coverage":min(x.coverage_fraction for x in t+h)})
    return {**base,"comparable_for_engineering_review":not blockers,"blockers":blockers,
       "results":results if not blockers else [],"diagnostics":diagnostics,
       "reference_label":p.reference_label,"model_calibrated":False,"external_peer_percentile":None,
       "tariff_normalized":False,"source_verification":"operator_declared_only",
       "assumptions":["Monthly OLS models with a common twelve-month reference CDD and occupancy schedule.",
          "Disjoint chronological holdout and marginal training-range checks do not establish source provenance or joint-domain uncertainty.",
          "No verified performance, external rating, energy saving, tariff or investment ranking. Independent review required."]}
