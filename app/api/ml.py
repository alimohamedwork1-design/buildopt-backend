from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.deps.auth import UserContext, get_required_user
from app.deps.guards import assert_building_access
from app.ml.anomaly_detector import AnomalyDetector
from app.ml.mpc_optimizer import MPCOptimizer
from app.models.schemas import (
    MLAnomalyRequest,
    MLAnomalyResponse,
    MLForecastRequest,
    MLOptimizeRequest,
    MLOptimizeResponse,
    ModelStatus,
)
from app.services import demo_mode, live_data_service

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/anomaly-detect", response_model=MLAnomalyResponse)
async def anomaly_detect(
    request: MLAnomalyRequest,
    user: UserContext = Depends(get_required_user),
) -> MLAnomalyResponse:
    assert_building_access(user, request.building_id)
    settings = get_settings()
    detector = AnomalyDetector(demo_mode=settings.demo_mode and user.allows_demo_data())
    anomalies = detector.detect(request.metrics)
    return MLAnomalyResponse(
        anomalies=anomalies,
        model_version="isolation_forest_runtime_v1" if not detector.demo_mode else "demo_rule_v1",
        demo_mode=detector.demo_mode,
    )


@router.post("/forecast")
async def ml_forecast(
    request: MLForecastRequest,
    user: UserContext = Depends(get_required_user),
) -> dict:
    assert_building_access(user, request.building_id)
    settings = get_settings()
    if user.allows_demo_data() and settings.demo_mode:
        forecast = demo_mode.get_energy_forecast(request.building_id, request.horizon_hours)
        return forecast.model_dump(mode="json")

    # The previous "LSTM" path generated a fixed synthetic profile in live mode.
    # Use the transparent historical baseline forecast until a trained/validated
    # model artifact is deployed.
    forecast = live_data_service.get_energy_forecast(
        request.building_id,
        request.horizon_hours,
        user=user,
    )
    if forecast is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "INSUFFICIENT_DATA",
                "message": "At least 24 observed hourly samples are required for live forecast.",
            },
        )
    return forecast.model_dump(mode="json")


@router.post("/optimize", response_model=MLOptimizeResponse)
async def optimize(
    request: MLOptimizeRequest,
    user: UserContext = Depends(get_required_user),
) -> MLOptimizeResponse:
    assert_building_access(user, request.building_id)
    settings = get_settings()
    if not (user.allows_demo_data() and settings.demo_mode):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SHADOW_ONLY",
                "message": "Generic MPC optimize endpoint is disabled in live mode. Use the evidence-aware shadow optimization workflow.",
            },
        )

    optimizer = MPCOptimizer(demo_mode=True)
    recommendations = optimizer.optimize(request.building_id, request.constraints)
    return MLOptimizeResponse(
        recommendations=recommendations,
        estimated_savings_pct=19.5,
        demo_mode=True,
    )


@router.get("/model-status", response_model=ModelStatus)
async def model_status() -> ModelStatus:
    settings = get_settings()
    if settings.demo_mode:
        return ModelStatus(
            anomaly_detector="demo_rule_v1",
            lstm_predictor="demo_only",
            fault_detector="demo_fdd",
            mpc_optimizer="demo_only",
        )
    return ModelStatus(
        anomaly_detector="isolation_forest_runtime_unvalidated",
        lstm_predictor="not_deployed_use_forecast_baseline_v1",
        fault_detector="quality_gated_rule_framework",
        mpc_optimizer="shadow_only",
    )
