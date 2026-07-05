from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional, Set

AccountMode = Literal["demo", "live"]
AccessLevel = Literal["read_only", "read_write"]


@dataclass
class UserContext:
    user_id: Optional[str] = None
    email: Optional[str] = None
    account_mode: AccountMode = "demo"
    access_level: AccessLevel = "read_write"
    roles: List[str] = field(default_factory=list)
    building_ids: List[str] = field(default_factory=list)
    enabled_modules: Set[str] = field(default_factory=set)
    authenticated: bool = False

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles

    @property
    def is_live_account(self) -> bool:
        return self.account_mode == "live"

    @property
    def is_read_only(self) -> bool:
        return self.access_level == "read_only"

    @property
    def has_buildings(self) -> bool:
        return len(self.building_ids) > 0

    def allows_demo_data(self) -> bool:
        from app.config import get_settings

        if self.is_live_account:
            return False
        return get_settings().demo_mode

    @classmethod
    def anonymous_demo(cls) -> UserContext:
        return cls(account_mode="demo", authenticated=False)

    @classmethod
    def anonymous_live(cls) -> UserContext:
        return cls(account_mode="live", authenticated=False)
