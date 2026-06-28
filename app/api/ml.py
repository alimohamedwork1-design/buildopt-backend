from fastapi import APIRouter

from app.config import get_settings
from app.ml.anomaly_detector import AnomalyDetector
from app.ml.fault_detector import FaultDetector
from app.ml.lstm_predictor import LSTMPredictor
from app.ml.mpc_optimizer import MPCOptimizer
from app.models.schemas import (
    MLAnomalyRequest,
    MLAnomalyResponse,
    MLForecastRequest,
    MLOptimizeRequest,
    MLOptimizeResponse,
    ModelStatus,
)
from app.services import demo_mode

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/anomaly-detect", response_model=MLAnomalyResponse)
async def anomaly_detect(request: MLAnomalyRequest) -> MLAnomalyResponse:
    settings = get_settings()
    detector = AnomalyDetector(demo_mode=settings.demo_mode)
    anomalies = detector.detect(request.metrics)
    return MLAnomalyResponse(anomalies=anomalies, model_version="1.0.0", demo_mode=settings.demo_mode)


@router.post("/forecast")
async def ml_forecast(request: MLForecastRequest) -> dict:
    settings = get_settings()
    if settings.demo_mode:
        forecast = demo_mode.get_energy_forecast(request.building_id, request.horizon_hours)
        return forecast.model_dump(mode="json")

    predictor = LSTMPredictor(demo_mode=False)
    return predictor.forecast(request.building_id, request.horizon_hours)


@router.post("/optimize", response_model=MLOptimizeResponse)
async def optimize(request: MLOptimizeRequest) -> MLOptimizeResponse:
    settings = get_settings()
    optimizer = MPCOptimizer(demo_mode=settings.demo_mode)
    recommendations = optimizer.optimize(request.building_id, request.constraints)
    return MLOptimizeResponse(
        recommendations=recommendations,
        estimated_savings_pct=19.5,
        demo_mode=settings.demo_mode,
    )


@router.get("/model-status", response_model=ModelStatus)
async def model_status() -> ModelStatus:
    settings = get_settings()
    suffix = "demo" if settings.demo_mode else "ready"
    return ModelStatus(
        anomaly_detector=f"isolation_forest_{suffix}",
        lstm_predictor=f"lstm_v1_{suffix}",
        fault_detector=f"xgboost_fdd_{suffix}",
        mpc_optimizer=f"mpc_v1_{suffix}",
    )
