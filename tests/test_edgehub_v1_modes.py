"""Mode parsing contract for Linux field gateway (no physical network required)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(mode: str):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "buildopt-edge"), EDGE_OPERATING_MODE=mode)
    return subprocess.run(
        [sys.executable, "-c", """
from app.config import EdgeSettings
s = EdgeSettings.from_env()
assert s.operating_mode in ('offline','hybrid','hybrid_4g')
assert s.operating_mode == __import__('os').environ['EDGE_OPERATING_MODE']
"""], env=env, cwd=str(ROOT / "buildopt-edge"), capture_output=True, text=True, timeout=15,
    )


def test_three_explicit_modes():
    for mode in ("offline", "hybrid", "hybrid_4g"):
        result = _run(mode)
        assert result.returncode == 0, result.stderr


def test_invalid_mode_rejected():
    env = dict(os.environ, PYTHONPATH=str(ROOT / "buildopt-edge"), EDGE_OPERATING_MODE="unsafe")
    result = subprocess.run(
        [sys.executable, "-c", "from app.config import EdgeSettings; EdgeSettings.from_env()"],
        env=env, cwd=str(ROOT / "buildopt-edge"), capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0
    assert "EDGE_OPERATING_MODE" in result.stderr
