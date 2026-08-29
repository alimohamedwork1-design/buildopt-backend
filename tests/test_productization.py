"""Productization pass — durable recommendations/savings, RBAC, tenant isolation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.recommendations_store import (
    Recommendation,
    RecommendationState,
    transition_recommendation,
    upsert_recommendation,
)
from app.services.savings_engine import SavingsState, compute_opportunity, transition_savings
from app.services.gcc_config import get_tariff, list_tariffs


@pytest.fixture
def client():
    return TestClient(app)


def test_durable_recommendation_persist_and_transition():
    rec = Recommendation(
        id="rec_test_1",
        building_id="b1",
        title="Test rec",
        description="Inspect AHU",
        state=RecommendationState.RECOMMENDED,
        recommended_action="Inspect AHU filter",
        confidence=0.8,
    )
    upsert_recommendation(rec)
    updated = transition_recommendation(
        "rec_test_1",
        RecommendationState.APPROVED,
        actor_user_id="u1",
        approved_by="engineer@test.com",
    )
    assert updated.state == RecommendationState.APPROVED
    assert updated.approved_by == "engineer@test.com"


def test_potential_savings_never_auto_verified():
    opp = compute_opportunity(
        opp_id="sv_test_1",
        building_id="b1",
        title="SAT reset",
        baseline_kwh=1000,
        expected_kwh=900,
        data_coverage_pct=90,
    )
    assert opp.state == SavingsState.POTENTIAL
    assert opp.verified_saving_aed is None
    assert opp.verification_status == "POTENTIAL"


def test_savings_transition_enforced():
    compute_opportunity(
        opp_id="sv_test_2",
        building_id="b1",
        title="Test",
        baseline_kwh=500,
        expected_kwh=450,
        data_coverage_pct=80,
    )
    approved = transition_savings("sv_test_2", SavingsState.APPROVED, actor_user_id="u1")
    assert approved.state == SavingsState.APPROVED
    with pytest.raises(ValueError):
        transition_savings("sv_test_2", SavingsState.VERIFIED, actor_user_id="u1")


def test_gcc_tariff_config_not_hardcoded_single():
    tariffs = list_tariffs()
    assert len(tariffs) >= 2
    dewa = get_tariff("UAE_DEWA")
    assert dewa and dewa["currency"] == "AED"


def test_recommendations_api_demo_or_auth(client):
    code = client.get("/api/v1/recommendations").status_code
    assert code in (200, 401)


def test_savings_api_demo_or_auth(client):
    code = client.get("/api/v1/savings/opportunities").status_code
    assert code in (200, 401)
