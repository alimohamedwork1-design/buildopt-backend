"""Facility graph validation, not automatic site discovery.

A graph is a proposed engineering mapping only. User-supplied point quality
or names never amount to independent field verification or meter calibration.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Literal

from pydantic import Field, model_validator

from app.services.decision_engine import StrictModel, SourceMode

AssetType = Literal["chiller","ahu","pump","meter","zone","cooling_tower","other"]
Relation = Literal["feeds","meters","serves","belongs_to","supplies"]


class FacilityAsset(StrictModel):
    asset_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=140)
    asset_type: AssetType


class FacilityEdge(StrictModel):
    source_asset_id: str
    target_asset_id: str
    relation: Relation


class FacilityPoint(StrictModel):
    point_id: str = Field(min_length=2, max_length=128)
    asset_id: str = Field(min_length=1, max_length=64)
    semantic_key: str = Field(min_length=3, max_length=128)
    unit: str = Field(min_length=1, max_length=32)
    source_system: str = Field(min_length=1, max_length=120)
    quality: Literal["good","stale","unknown","invalid"] = "unknown"
    source_timestamp: datetime | None = None


class FacilityGraphRequest(StrictModel):
    building_id: str = Field(min_length=1, max_length=128)
    assets: list[FacilityAsset] = Field(min_length=1,max_length=100)
    edges: list[FacilityEdge] = Field(default_factory=list,max_length=200)
    points: list[FacilityPoint] = Field(default_factory=list,max_length=500)
    source_mode: SourceMode
    read_only: Literal[True] = True

    @model_validator(mode="after")
    def consistent_references(self):
        ids = [asset.asset_id for asset in self.assets]
        if len(ids)!=len(set(ids)):
            raise ValueError("Duplicate asset identifiers are not allowed")
        identity = set(ids)
        point_ids=[p.point_id for p in self.points]
        if len(point_ids)!=len(set(point_ids)):
            raise ValueError("Duplicate point identifiers are not allowed")
        for point in self.points:
            if point.asset_id not in identity:
                raise ValueError("Point references unknown asset")
        seen_edges=set()
        for edge in self.edges:
            if edge.source_asset_id not in identity or edge.target_asset_id not in identity:
                raise ValueError("Edge references unknown asset")
            if edge.source_asset_id==edge.target_asset_id:
                raise ValueError("Self-relations are not allowed")
            tag=(edge.source_asset_id,edge.target_asset_id,edge.relation)
            if tag in seen_edges:
                raise ValueError("Duplicate relation")
            seen_edges.add(tag)
        return self


def check_facility_graph(request:FacilityGraphRequest, *, now: datetime|None=None)->dict:
    now=now or datetime.now(timezone.utc)
    quality_issues=[]
    for point in request.points:
        if point.quality!="good":
            quality_issues.append({"point_id":point.point_id,"reason":"not_good_quality"})
            continue
        stamp=point.source_timestamp
        if stamp is None or stamp.tzinfo is None:
            quality_issues.append({"point_id":point.point_id,"reason":"missing_timezone_timestamp"})
        elif stamp>now+timedelta(minutes=1):
            quality_issues.append({"point_id":point.point_id,"reason":"future_timestamp"})
        elif now-stamp>timedelta(minutes=15):
            quality_issues.append({"point_id":point.point_id,"reason":"stale_telemetry"})
    return {
        "building_id":request.building_id,
        "source_mode":request.source_mode,
        "asset_count":len(request.assets),
        "relation_count":len(request.edges),
        "point_count":len(request.points),
        "quality_issues":quality_issues,
        "engineering_review_ready":bool(request.points) and not quality_issues and bool(request.edges),
        "field_validated":False,
        "writeback_enabled":False,
        "missing_evidence":[
            "Owner-approved access, point maps, meter calibration and signed reviewer acceptance are independently required."
        ],
        "graph":{
            "nodes":[{"id":a.asset_id,"type":a.asset_type,"name":a.name} for a in request.assets],
            "links":[{"from":e.source_asset_id,"to":e.target_asset_id,"relation":e.relation} for e in request.edges],
        },
    }
