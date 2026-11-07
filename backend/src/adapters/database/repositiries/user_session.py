from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete

from adapters.database.models import UserAuthChallengeModel, UserRefreshTokenModel
from domain.entities.auth import AuthProvider
from domain.security import TokenManager
from ports import DatabaseManagerInterface


class UserSessionRepository:
    def __init__(self, db: DatabaseManagerInterface) -> None:
        self._db = db

    async def add_challenge(
        self, nonce: str, provider: AuthProvider, expires_at: datetime
    ) -> None:
        await self._db.execute(
            delete(UserAuthChallengeModel).where(
                UserAuthChallengeModel.expires_at <= datetime.now(UTC)
            )
        )
        self._db.add(
            UserAuthChallengeModel(
                nonce_hash=TokenManager.hash_token(nonce),
                provider=provider.value,
                expires_at=expires_at,
            )
        )
        await self._db.flush()

    async def consume_challenge(self, nonce: str, provider: AuthProvider) -> bool:
        # DELETE RETURNING забезпечує одноразовість навіть між API workers.
        result = await self._db.scalar(
            delete(UserAuthChallengeModel)
            .where(
                UserAuthChallengeModel.nonce_hash == TokenManager.hash_token(nonce),
                UserAuthChallengeModel.provider == provider.value,
                UserAuthChallengeModel.expires_at > datetime.now(UTC),
            )
            .returning(UserAuthChallengeModel.nonce_hash)
        )
        return result is not None

    async def add_refresh_token(
        self, user_id: UUID, token: str, expires_at: datetime
    ) -> None:
        await self._db.execute(
            delete(UserRefreshTokenModel).where(
                UserRefreshTokenModel.expires_at <= datetime.now(UTC)
            )
        )
        instance = UserRefreshTokenModel(user_id=user_id, expires_at=expires_at)
        instance.token = token
        self._db.add(instance)
        await self._db.flush()

    async def consume_refresh_token(self, user_id: UUID, token: str) -> bool:
        result = await self._db.scalar(
            delete(UserRefreshTokenModel)
            .where(
                UserRefreshTokenModel.user_id == user_id,
                UserRefreshTokenModel._hashed_token == TokenManager.hash_token(token),
                UserRefreshTokenModel.expires_at > datetime.now(UTC),
            )
            .returning(UserRefreshTokenModel.id)
        )
        return result is not None
