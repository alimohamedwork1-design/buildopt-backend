import pytest

from app.services.incident_metadata import ErrorSeverity, classify_operational_error


def test_safe_incident_contains_no_exception_payload():
    incident = classify_operational_error(component="telemetry", error_code="SOURCE_TIMEOUT", severity=ErrorSeverity.ERROR)
    assert incident.component == "telemetry"
    assert incident.error_code == "SOURCE_TIMEOUT"
    assert incident.incident_id
    assert not hasattr(incident, "stack_trace")


def test_unbounded_or_sensitive_identifiers_rejected():
    with pytest.raises(ValueError):
        classify_operational_error(component="telemetry", error_code="Authorization: Bearer secret", severity=ErrorSeverity.ERROR)
