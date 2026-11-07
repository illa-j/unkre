from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.entities.admin import Admin


class AdminRepositoryInterface(Protocol):
    async def get_admin(self, admin_id: UUID) -> Admin | None: ...

    async def find_by_username(self, username: str) -> Admin | None: ...

    async def create_admin(self, admin: Admin) -> Admin: ...

    async def update_password_hash(
        self, admin_id: UUID, old_hash: str, new_hash: str
    ) -> None: ...


class AdminSessionRepositoryInterface(Protocol):
    async def add_refresh_token(
        self, admin_id: UUID, token: str, expires_at: datetime
    ) -> None: ...

    async def consume_refresh_token(self, admin_id: UUID, token: str) -> bool: ...
