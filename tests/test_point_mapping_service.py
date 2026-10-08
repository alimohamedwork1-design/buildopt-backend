from app.services.point_mapping_service import suggest_point_mapping


def test_ahu_supply_air_temperature_is_review_only():
    suggestion = suggest_point_mapping("AHU-01_SAT")
    assert suggestion.equipment_id == "AHU01"
    assert suggestion.semantic_key == "supply_air_temp"
    assert suggestion.review_status == "PENDING_REVIEW"


def test_unknown_points_are_not_assigned():
    suggestion = suggest_point_mapping("AHU-01_???")
    assert suggestion.semantic_key is None
    assert suggestion.confidence == 0


def test_mapping_without_equipment_requires_review():
    suggestion = suggest_point_mapping("RAT")
    assert suggestion.semantic_key == "return_air_temp"
    assert suggestion.equipment_id is None
    assert suggestion.confidence < 0.6


def test_empty_input_is_unmapped():
    suggestion = suggest_point_mapping("  ")
    assert suggestion.semantic_key is None
    assert suggestion.review_status == "PENDING_REVIEW"
