from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class BilingualMessage(BaseModel):
    en: str
    ar: str


class HVACData(BaseModel):
    supply_air_temp: float
    return_air_temp: float
    delta_t: float
    power_kw: float
    cop: float


class EnergyData(BaseModel):
    total_kw: float
    hvac_kw: float
    lighting_kw: float
    other_kw: float
    tariff_rate: float
    cost_per_hour: float


class EnvironmentData(BaseModel):
    temp_c: float
    humidity_pct: float
    co2_ppm: int
    pm25: float


class LiveBuildingData(BaseModel):
    building_id: str
    timestamp: datetime
    hvac: HVACData
    energy: EnergyData
    environment: EnvironmentData
    active_alerts: int
    demo_mode: bool


class BuildingSummary(BaseModel):
    id: str
    name: str
    location: str
    floors: int
    area_sqm: float
    status: Literal["online", "offline", "maintenance"]
    energy_savings_pct: float
    active_alerts: int


class BuildingDetail(BuildingSummary):
    bms_type: str
    installed_capacity_kw: float
    last_updated: datetime


class ControlCommand(BaseModel):
    command: str
    target: str
    value: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ControlResponse(BaseModel):
    success: bool
    message: BilingualMessage
    building_id: str
    command: str


class MetricPoint(BaseModel):
    timestamp: datetime
    value: float
    metric: str


class BuildingMetrics(BaseModel):
    building_id: str
    period: str
    metrics: List[MetricPoint]


class EnergyConsumption(BaseModel):
    timestamp: datetime
    total_kw: float
    hvac_kw: float
    lighting_kw: float
    other_kw: float
    cost_aed_per_hour: float
    demo_mode: bool


class EnergyForecastPoint(BaseModel):
    timestamp: datetime
    predicted_kw: float
    confidence: float


class EnergyForecast(BaseModel):
    building_id: str
    horizon_hours: int
    forecast: List[EnergyForecastPoint]
    demo_mode: bool


class DewaTariffBreakdown(BaseModel):
    period: str
    rate_aed_per_kwh: float
    consumption_kwh: float
    cost_aed: float


class DewaTariffResponse(BaseModel):
    month: str
    is_summer: bool
    peak: DewaTariffBreakdown
    off_peak: DewaTariffBreakdown
    demand_charge_aed: float
    total_cost_aed: float
    demo_mode: bool


class EnergySavings(BaseModel):
    baseline_kwh: float
    actual_kwh: float
    savings_kwh: float
    savings_pct: float
    cost_saved_aed: float
    demo_mode: bool


class EquipmentSummary(BaseModel):
    id: str
    name: str
    type: str
    building_id: str
    status: Literal["running", "stopped", "fault", "maintenance"]
    power_kw: float
    efficiency: float


class EquipmentDetail(EquipmentSummary):
    setpoint: float
    current_value: float
    last_maintenance: datetime
    fault_code: Optional[str] = None


class SetpointUpdate(BaseModel):
    setpoint: float
    reason: Optional[str] = None


class Alert(BaseModel):
    id: str
    building_id: str
    equipment_id: Optional[str] = None
    severity: Literal["critical", "warning", "info"]
    category: str
    title: str
    message: str
    message_ar: str
    timestamp: datetime
    acknowledged: bool


class AlertAcknowledge(BaseModel):
    acknowledged_by: Optional[str] = None
    notes: Optional[str] = None


class FDDResult(BaseModel):
    rule_id: str
    category: str
    equipment_id: str
    severity: Literal["critical", "warning", "info"]
    description: str
    description_ar: str
    confidence: float
    detected_at: datetime


class MLAnomalyRequest(BaseModel):
    building_id: str
    metrics: List[Dict[str, float]]


class MLAnomalyResponse(BaseModel):
    anomalies: List[Dict[str, Any]]
    model_version: str
    demo_mode: bool


class MLForecastRequest(BaseModel):
    building_id: str
    horizon_hours: int = 24


class MLOptimizeRequest(BaseModel):
    building_id: str
    constraints: Dict[str, Any] = Field(default_factory=dict)


class MLOptimizeResponse(BaseModel):
    recommendations: List[Dict[str, Any]]
    estimated_savings_pct: float
    demo_mode: bool


class ModelStatus(BaseModel):
    anomaly_detector: str
    lstm_predictor: str
    fault_detector: str
    mpc_optimizer: str


class JCIObject(BaseModel):
    id: str
    name: str
    type: str
    present_value: Optional[Any] = None


class JCICommand(BaseModel):
    attribute: str = "presentValue"
    value: Any


class PrayerTimes(BaseModel):
    date: str
    location: str
    times: Dict[str, str]
    hvac_adjustments: List[Dict[str, Any]]


class RamadanMode(BaseModel):
    active: bool
    hijri_date: str
    schedule: List[Dict[str, Any]]


class SandstormAlert(BaseModel):
    active: bool
    pm10: float
    threshold: float
    actions: List[str]
    timestamp: datetime


class HealthResponse(BaseModel):
    status: str
    version: str
    demo_mode: bool
    timestamp: datetime


class ProtocolStatus(BaseModel):
    bacnet: str
    modbus: str
    mqtt: str
    jci_metasys: str
