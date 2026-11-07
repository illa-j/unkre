from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete

from adapters.database.models import AdminRefreshTokenModel
from adapters.database.repositiries import CrudRepository
from domain.security import TokenManager
from ports import DatabaseManagerInterface


class AdminRefreshTokenRepository(CrudRepository[AdminRefreshTokenModel, int]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, AdminRefreshTokenModel)

    async def add_refresh_token(
        self, admin_id: UUID, token: str, expires_at: datetime
    ) -> None:
        await self._db.execute(
            delete(AdminRefreshTokenModel).where(
                AdminRefreshTokenModel.expires_at <= datetime.now(UTC)
            )
        )
        model = AdminRefreshTokenModel(admin_id=admin_id, expires_at=expires_at)
        model.token = token
        self._db.add(model)
        await self._db.flush()

    async def consume_refresh_token(self, admin_id: UUID, token: str) -> bool:
        result = await self._db.scalar(
            delete(AdminRefreshTokenModel)
            .where(
                AdminRefreshTokenModel.admin_id == admin_id,
                AdminRefreshTokenModel._hashed_token == TokenManager.hash_token(token),
                AdminRefreshTokenModel.expires_at > datetime.now(UTC),
            )
            .returning(AdminRefreshTokenModel.id)
        )
        return result is not None
