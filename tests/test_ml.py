from app.ml.anomaly_detector import AnomalyDetector
from app.ml.fault_detector import FaultDetector
from app.ml.mpc_optimizer import MPCOptimizer


def test_anomaly_detector_demo():
    detector = AnomalyDetector(demo_mode=True)
    metrics = [{"total_kw": 950, "hvac_kw": 200, "temp_c": 23}]
    results = detector.detect(metrics)
    assert len(results) == 1
    assert results[0]["is_anomaly"] is True


def test_fault_detector_cop():
    detector = FaultDetector(demo_mode=False)
    faults = detector.evaluate({"cop": 2.5})
    assert any(f["rule_id"] == "FDD-007" for f in faults)


def test_optimizer_is_shadow_only_and_does_not_invent_savings():
    optimizer = MPCOptimizer(demo_mode=False)
    recs = optimizer.optimize(
        "building-01",
        {"min_cop": 3.2, "current_cop": 2.8, "current_supply_temp": 14.0},
    )
    assert len(recs) >= 1
    assert all(r["candidate_only"] is True for r in recs)
    assert all(r["writeback_allowed"] is False for r in recs)
    assert all(r["engine_mode"] == "bounded_rule_advisor_shadow_only" for r in recs)


def test_optimizer_refuses_to_fake_candidate_without_state():
    optimizer = MPCOptimizer(demo_mode=False)
    recs = optimizer.optimize("building-01", {"min_cop": 3.2})
    assert len(recs) == 1
    assert recs[0]["action"] == "collect_operating_state"
    assert recs[0]["writeback_allowed"] is False
