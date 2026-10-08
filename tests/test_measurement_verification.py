import pytest

from app.services.measurement_verification import calculate_eui, estimate_unverified_savings


def test_missing_baseline_cannot_generate_savings():
    assert estimate_unverified_savings(baseline_kwh=None, measured_kwh=100) is None
    assert estimate_unverified_savings(baseline_kwh=0, measured_kwh=100) is None


def test_difference_is_not_verified_savings():
    result = estimate_unverified_savings(baseline_kwh=1000, measured_kwh=900)
    assert result.estimated_savings_kwh == 100
    assert result.estimated_savings_pct == 10
    assert result.verification_status == "UNVERIFIED"


def test_review_ready_is_still_not_verified():
    result = estimate_unverified_savings(
        baseline_kwh=1000, measured_kwh=900,
        baseline_adjusted=True, sufficient_coverage=True,
    )
    assert result.verification_status == "READY_FOR_INDEPENDENT_REVIEW"


def test_negative_savings_is_preserved():
    result = estimate_unverified_savings(baseline_kwh=1000, measured_kwh=1200)
    assert result.estimated_savings_kwh == -200


def test_eui_is_raw_not_normalized():
    result = calculate_eui(building_id="B1", energy_kwh=5000, conditioned_area_m2=1000)
    assert result.eui_kwh_m2 == 5
    assert result.comparison_status == "RAW_EUI_NOT_NORMALIZED"


def test_bad_floor_area_rejected():
    with pytest.raises(ValueError):
        calculate_eui(building_id="B1", energy_kwh=5000, conditioned_area_m2=0)
