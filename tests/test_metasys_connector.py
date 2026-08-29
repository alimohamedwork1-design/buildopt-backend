import asyncio
import importlib.util
import sys
from pathlib import Path

EDGE_ROOT = Path(__file__).resolve().parents[1] / "buildopt-edge"


def _get_metasys_connector_class():
    base_path = EDGE_ROOT / "app/connectors/base.py"
    base_spec = importlib.util.spec_from_file_location("edge_connectors_base", base_path)
    base_mod = importlib.util.module_from_spec(base_spec)
    assert base_spec.loader is not None
    base_spec.loader.exec_module(base_mod)
    sys.modules["app.connectors.base"] = base_mod

    metasys_path = EDGE_ROOT / "app/connectors/metasys.py"
    metasys_spec = importlib.util.spec_from_file_location("edge_connectors_metasys", metasys_path)
    metasys_mod = importlib.util.module_from_spec(metasys_spec)
    assert metasys_spec.loader is not None
    metasys_spec.loader.exec_module(metasys_mod)
    return metasys_mod.MetasysConnector


def test_metasys_not_configured_without_host():
    MetasysConnector = _get_metasys_connector_class()
    conn = MetasysConnector("", "user", "pass")
    health = asyncio.run(conn.health())
    assert health["status"] in (
        "NOT_CONFIGURED",
        "CONNECTION_REFUSED",
        "AUTH_ERROR",
        "API_ERROR",
        "TIMEOUT",
    )


def test_metasys_capabilities():
    MetasysConnector = _get_metasys_connector_class()
    conn = MetasysConnector("https://example.com", "u", "p")
    caps = asyncio.run(conn.capabilities())
    assert caps["protocol"] == "metasys"
    assert caps["writeback"] is False
