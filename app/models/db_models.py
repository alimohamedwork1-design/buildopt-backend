"""Database record models for persistence layers."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BuildingRecord(BaseModel):
    id: str
    name: str
    location: str
    floors: int
    area_sqm: float
    bms_type: str
    installed_capacity_kw: float
    created_at: datetime
    updated_at: datetime


class EquipmentRecord(BaseModel):
    id: str
    building_id: str
    name: str
    type: str
    setpoint: float
    status: str
    created_at: datetime


class AlertRecord(BaseModel):
    id: str
    building_id: str
    equipment_id: Optional[str]
    severity: str
    category: str
    title: str
    message: str
    message_ar: str
    acknowledged: bool
    created_at: datetime
