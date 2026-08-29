"""Central DEMO vs LIVE data policy — single source of truth for telemetry access."""

from __future__ import annotations

from typing import Literal, Optional

from app.config import get_settings
from app.models.user_context import UserContext

DataMode = Literal["DEMO", "LIVE"]
DataOrigin = Literal[
    "METASYS",
    "BACNET",
    "MODBUS",
    "MQTT",
    "OPCUA",
    "IMPORT",
    "MANUAL",
    "INFLUX",
    "EDGE",
    "SIMULATED",
]


def resolve_data_mode(user: Optional[UserContext] = None) -> DataMode:
    if user is not None and user.is_live_account:
        return "LIVE"
    settings = get_settings()
    if settings.demo_mode and (user is None or user.allows_demo_data()):
        return "DEMO"
    return "LIVE"


def allows_simulated_telemetry(user: Optional[UserContext] = None) -> bool:
    return resolve_data_mode(user) == "DEMO"


def requires_real_telemetry(user: Optional[UserContext] = None) -> bool:
    return resolve_data_mode(user) == "LIVE"
