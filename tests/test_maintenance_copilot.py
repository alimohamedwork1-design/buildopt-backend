from datetime import datetime, timezone

import pytest

from app.services.maintenance_copilot import FaultEvidence, prepare_maintenance_draft


def test_draft_requires_human_review_and_preserves_evidence():
    event = FaultEvidence(
        fault_id="F-1", asset_id="AHU-1", rule_id="cooling_valve_leak",
        observed_at=datetime(2026, 10, 8, tzinfo=timezone.utc),
        measured_points=["SAT", "SAT", "CHWV"],
    )
    draft = prepare_maintenance_draft(event)
    assert draft.review_status == "PENDING_HUMAN_REVIEW"
    assert draft.evidence_refs == ["SAT", "CHWV"]
    assert draft.confidence is None
    assert not hasattr(draft, "execute")


def test_missing_measurements_rejected():
    event = FaultEvidence(
        fault_id="F-2", asset_id="AHU-1", rule_id="sensor_fault",
        observed_at=datetime(2026, 10, 8, tzinfo=timezone.utc),
    )
    with pytest.raises(ValueError):
        prepare_maintenance_draft(event)
