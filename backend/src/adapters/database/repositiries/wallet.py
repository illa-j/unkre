from uuid import UUID

from sqlalchemy import select

from adapters.database.models import WalletModel
from adapters.database.repositiries import CrudRepository
from domain.entities.payment import Wallet
from ports import DatabaseManagerInterface


class WalletRepository(CrudRepository[WalletModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, WalletModel)

    async def get_wallet(self, wallet_id: UUID) -> Wallet | None:
        row = await self.get(wallet_id)
        return self._to_entity(row)

    async def get_by_user(self, user_id: UUID) -> Wallet | None:
        return self._to_entity(
            await self._db.scalar(
                select(WalletModel).where(WalletModel.user_id == user_id)
            )
        )

    async def get_for_update(self, wallet_id: UUID) -> Wallet | None:
        return self._to_entity(
            await self._db.scalar(
                select(WalletModel)
                .where(WalletModel.id == wallet_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    @staticmethod
    def _to_entity(row: WalletModel | None) -> Wallet | None:
        return (
            Wallet(id=row.id, user_id=row.user_id, credits=row.credits)
            if row is not None
            else None
        )
