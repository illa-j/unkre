from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.entities.auth import AuthProvider, SocialIdentity
from domain.entities.user import User


class UserRepositoryInterface(Protocol):
    async def get_user(self, user_id: UUID) -> User | None: ...

    async def find_identity(self, identity: SocialIdentity) -> User | None: ...

    async def find_by_referral_code(self, code: str) -> User | None: ...

    async def register(self, identity: SocialIdentity, credits: int) -> User: ...

    async def update_identity(
        self, user_id: UUID, identity: SocialIdentity
    ) -> User: ...

    async def link_identity(
        self, user_id: UUID, identity: SocialIdentity
    ) -> User: ...


class UserSessionRepositoryInterface(Protocol):
    async def add_challenge(
        self, nonce: str, provider: AuthProvider, expires_at: datetime
    ) -> None: ...

    async def consume_challenge(self, nonce: str, provider: AuthProvider) -> bool: ...

    async def add_refresh_token(
        self, user_id: UUID, token: str, expires_at: datetime
    ) -> None: ...

    async def consume_refresh_token(self, user_id: UUID, token: str) -> bool: ...
