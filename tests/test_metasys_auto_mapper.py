from app.services.metasys_auto_mapper import flatten_metasys_objects, suggest_mappings


def test_suggest_mappings_from_names():
    objects = [
        {"id": "a1", "name": "AHU1-SAT", "type": "AI", "label": "AHU1-SAT Analog Input"},
        {"id": "a2", "name": "AHU1-RAT", "type": "AI", "label": "AHU1-RAT"},
        {"id": "p1", "name": "Main-Total-KW", "type": "AI", "label": "Main-Total-KW"},
    ]
    mapped = suggest_mappings(objects, {}, merge=False)
    assert mapped["supply_air_temp"] == "a1"
    assert mapped["return_air_temp"] == "a2"
    assert mapped["total_kw"] == "p1"


def test_flatten_nested_payload():
    payload = {
        "items": [
            {"id": "x1", "name": "Zone-CO2", "type": "AI"},
            {"children": [{"id": "x2", "name": "CH1-KW", "type": "AI"}]},
        ]
    }
    flat = flatten_metasys_objects(payload)
    assert len(flat) == 2
    assert {o["id"] for o in flat} == {"x1", "x2"}
