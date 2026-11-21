"""Prove simulation failure detection without connecting to any controller."""
import pytest
from app.services.integration_lab import (
    PROTOCOLS, SCENARIOS, evaluate_fixture, generate_fixture
)


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_nominal_synthetic_protocols_are_quality_valid(protocol):
    fixture = generate_fixture(protocol, "healthy")
    report = evaluate_fixture(fixture)
    assert report["lab_regression_passed"]
    assert report["quality_accepted"] == 12
    assert report["completeness"] == 1
    assert report["device_connections_attempted"] == 0
    assert report["writeback_enabled"] is False
    assert report["field_validated"] is False
    assert fixture["simulated"] is True


@pytest.mark.parametrize("scenario", [s for s in SCENARIOS if s != "healthy"])
def test_each_fault_has_detectable_quality_failure(scenario):
    report = evaluate_fixture(generate_fixture("bacnet_ip", scenario))
    assert not report["lab_regression_passed"]
    assert report["issues"]
    assert report["field_validated"] is False


def test_duplicate_does_not_increase_completeness():
    report = evaluate_fixture(generate_fixture("modbus_tcp", "duplicate_event"))
    assert report["received_samples"] == 13
    assert report["unique_samples"] == 12
    assert report["completeness"] == 1
    assert any(x["reason"] == "duplicate_event" for x in report["issues"])


def test_packet_loss_is_detected_without_fabricated_values():
    report = evaluate_fixture(generate_fixture("mqtt", "packet_loss"))
    assert report["received_samples"] == 8
    assert report["completeness"] == pytest.approx(8 / 12, abs=0.001)


def test_no_connection_is_never_a_good_status():
    report = evaluate_fixture(generate_fixture("opc_ua", "offline"))
    assert report["quality_accepted"] == 0
    assert any(x["reason"] == "connector_offline" for x in report["issues"])


def test_no_real_site_payload_accepted_by_lab_evaluator():
    fixture = generate_fixture("rest", "healthy")
    fixture["simulated"] = False
    with pytest.raises(ValueError):
        evaluate_fixture(fixture)


def test_invalid_protocol_and_scenario_do_not_fall_back_to_success():
    with pytest.raises(ValueError):
        generate_fixture("unknown_oem", "healthy")
    with pytest.raises(ValueError):
        generate_fixture("bacnet_ip", "autopilot")
