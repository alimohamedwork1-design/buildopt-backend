"""Read-only digital twin scene asset registry.

Asset positions and 3D models must be supplied by the site. No invented
geometry, equipment telemetry, or control surfaces are generated.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class TwinAsset(BaseModel):
    asset_id: str = Field(min_length=1)
    building_id: str = Field(min_length=1)
    floor_id: str = Field(min_length=1)
    equipment_type: str = Field(min_length=1)
    model_node_id: Optional[str] = None
    point_ids: list[str] = Field(default_factory=list)
    mapping_approved: bool = False


class TwinScene(BaseModel):
    building_id: str = Field(min_length=1)
    model_uri: Optional[str] = None
    assets: list[TwinAsset] = Field(default_factory=list)
    data_status: str = "UNVERIFIED"

    @model_validator(mode="after")
    def check_assets(self):
        if any(asset.building_id != self.building_id for asset in self.assets):
            raise ValueError("Cross-building twin asset reference")
        ids = [asset.asset_id for asset in self.assets]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate asset identifiers")
        if self.model_uri and not self.model_uri.startswith(("https://", "/")):
            raise ValueError("Twin model must use a trusted application path or HTTPS")
        return self

    def mapped_asset_count(self) -> int:
        return sum(bool(a.mapping_approved and a.model_node_id) for a in self.assets)
