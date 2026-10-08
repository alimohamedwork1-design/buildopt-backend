import pytest
from pydantic import ValidationError

from app.services.digital_twin_registry import TwinAsset, TwinScene


def test_twin_mapping_requires_explicit_approval():
    scene = TwinScene(building_id="B1", assets=[TwinAsset(
        asset_id="AHU1", building_id="B1", floor_id="L1",
        equipment_type="AHU", model_node_id="mesh-1",
    )])
    assert scene.mapped_asset_count() == 0
    assert scene.data_status == "UNVERIFIED"


def test_cross_building_asset_rejected():
    with pytest.raises(ValidationError):
        TwinScene(building_id="B1", assets=[TwinAsset(
            asset_id="AHU1", building_id="B2", floor_id="L1", equipment_type="AHU",
        )])


def test_duplicate_asset_ids_rejected():
    asset = TwinAsset(asset_id="AHU1", building_id="B1", floor_id="L1", equipment_type="AHU")
    with pytest.raises(ValidationError):
        TwinScene(building_id="B1", assets=[asset, asset])


def test_untrusted_model_url_rejected():
    with pytest.raises(ValidationError):
        TwinScene(building_id="B1", model_uri="http://untrusted.example/model.glb")
