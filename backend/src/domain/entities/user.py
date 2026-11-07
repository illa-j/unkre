from dataclasses import dataclass, field
from datetime import UTC, datetime
from secrets import token_hex
from uuid import UUID, uuid7


@dataclass(kw_only=True)
class User:
    first_name: str
    id: UUID = field(default_factory=uuid7)
    telegram_id: int | None = None
    google_sub: str | None = None
    google_email: str | None = None
    username: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    photo_url: str | None = None
    is_premium: bool | None = None
    allows_write_to_pm: bool | None = None
    added_to_attachment_menu: bool | None = None
    credits: int = 0
    referral_code: str = field(default_factory=lambda: token_hex(12))
    is_blocked: bool = False
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_active_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class UserRefreshToken:
    user_id: UUID
    expires_at: datetime
    id: int | None = None
