"""Credential access — environment / OS secrets only; never log passwords."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SecretRef:
    source: str
    username: str
    password: str
    host: str = ""


def load_metasys_credentials(
    host: str = "",
    username: str = "",
    password: str = "",
) -> Optional[SecretRef]:
    h = host or os.getenv("METASYS_HOST", "")
    u = username or os.getenv("METASYS_USERNAME", "")
    p = password or os.getenv("METASYS_PASSWORD", "")
    if not h or not u or not p:
        return None
    return SecretRef(source="env", username=u, password=p, host=h.rstrip("/"))
