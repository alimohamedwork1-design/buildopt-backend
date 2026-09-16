from fastapi import APIRouter, Depends

from app.config import get_settings
from app.deps.auth import UserContext, get_optional_user
from app.deps.guards import assert_building_access
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
async def anomaly_detect(
    request: MLAnomalyRequest,
    user: UserContext = Depends(get_optional_user),
) -> MLAnomalyResponse:
    settings = get_settings()
    if not settings.demo_mode:
        assert_building_access(user, request.building_id)
    detector = AnomalyDetector(demo_mode=settings.demo_mode)
    anomalies = detector.detect(request.metrics)
    version = "threshold_demo" if settings.demo_mode else "isolation_forest_fit_on_request_pilot"
    return MLAnomalyResponse(anomalies=anomalies, model_version=version, demo_mode=settings.demo_mode)


@router.post("/forecast")
async def ml_forecast(
    request: MLForecastRequest,
    user: UserContext = Depends(get_optional_user),
) -> dict:
    settings = get_settings()
    if settings.demo_mode:
        forecast = demo_mode.get_energy_forecast(request.building_id, request.horizon_hours)
        payload = forecast.model_dump(mode="json")
        payload.update({"available": True, "method": "demo_simulation", "model_version": "demo"})
        return payload

    assert_building_access(user, request.building_id)
    predictor = LSTMPredictor(demo_mode=False)
    return predictor.forecast(request.building_id, request.horizon_hours)


@router.post("/optimize", response_model=MLOptimizeResponse)
async def optimize(
    request: MLOptimizeRequest,
    user: UserContext = Depends(get_optional_user),
) -> MLOptimizeResponse:
    settings = get_settings()
    if not settings.demo_mode:
        assert_building_access(user, request.building_id)
    optimizer = MPCOptimizer(demo_mode=settings.demo_mode)
    recommendations = optimizer.optimize(request.building_id, request.constraints)
    return MLOptimizeResponse(
        recommendations=recommendations,
        # Demo can show a simulated value. Live mode does not invent savings; verified
        # savings belong to the dedicated M&V workflow.
        estimated_savings_pct=19.5 if settings.demo_mode else None,
        demo_mode=settings.demo_mode,
        engine_mode=optimizer.engine_mode,
        writeback_allowed=False,
    )


@router.get("/model-status", response_model=ModelStatus)
async def model_status() -> ModelStatus:
    settings = get_settings()
    if settings.demo_mode:
        return ModelStatus(
            anomaly_detector="threshold_demo_simulation",
            lstm_predictor="demo_forecast_simulation",
            fault_detector="rule_fdd_demo",
            mpc_optimizer="bounded_rule_advisor_demo",
        )

    # Product-truth labels: do not advertise algorithms that are not actually loaded.
    return ModelStatus(
        anomaly_detector="isolation_forest_fit_on_request_pilot",
        lstm_predictor="history_gradient_boosting_pilot",
        fault_detector="rule_based_fdd_v1",
        mpc_optimizer="bounded_rule_advisor_shadow_only",
    )
