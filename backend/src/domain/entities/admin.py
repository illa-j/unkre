from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(kw_only=True)
class Admin:
    username: str
    id: UUID | None = None
    is_owner: bool = False
    password: str | None = field(default=None, repr=False)
    hashed_password: str | None = field(default=None, repr=False)


@dataclass(frozen=True, kw_only=True)
class AdminRefreshToken:
    admin_id: UUID
    expires_at: datetime
    id: int | None = None
