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


def test_mpc_optimizer():
    optimizer = MPCOptimizer(demo_mode=True)
    recs = optimizer.optimize("burj-khalifa-01", {"min_cop": 3.2})
    assert len(recs) >= 2
