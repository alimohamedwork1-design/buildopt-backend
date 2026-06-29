"""Tests for industrial refrigeration Metasys auto-mapper."""

from app.services.refrigeration_auto_mapper import REFRIGERATION_LOGICAL_KEYS, suggest_refrigeration_mappings


def test_refrigeration_logical_keys_count():
    assert len(REFRIGERATION_LOGICAL_KEYS) == 9


def test_suggest_refrigeration_mappings_finds_superheat():
    objects = [
        {"id": "obj-1", "name": "Rack Superheat", "type": "AI", "label": "Rack Superheat AI"},
        {"id": "obj-2", "name": "Cold Room Box Temp", "type": "AI", "label": "Cold Room Box Temp AI"},
    ]
    mapped = suggest_refrigeration_mappings(objects, merge=False)
    assert mapped.get("superheat_k") == "obj-1"
    assert mapped.get("evap_temp_c") == "obj-2"
