from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID


@dataclass(kw_only=True)
class SystemSetting:
    key: str
    value: Any
    description: str | None = None
    updated_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class SystemSettingDefaults:
    initial_credits: int
    inviter_credits: int
    invitee_credits: int
    crypto_price_per_credit: str | None
    crypto_currency: str
    stars_price_per_credit: int | None
    crypto_min_amount: str
    stars_min_amount: int


@dataclass(frozen=True, kw_only=True)
class SystemSettingView:
    key: str
    value: Any
    default: Any
    description: str
    source: Literal["default", "database"]
    updated_by: UUID | None = None
    updated_at: datetime | None = None

