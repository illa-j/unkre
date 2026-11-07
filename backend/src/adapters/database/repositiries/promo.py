from dataclasses import replace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from adapters.database.models import PromoCodeModel, PromoRedemptionModel
from adapters.database.repositiries import CrudRepository
from domain.entities.promo import PromoCode, PromoRedemption, normalize_promo_code
from domain.exceptions.promo import (
    PromoCodeAlreadyRedeemedError,
    PromoCodeDuplicateError,
)
from ports import DatabaseManagerInterface


class PromoCodeRepository(CrudRepository[PromoCodeModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, PromoCodeModel)

    async def create_code(self, code: PromoCode) -> PromoCode:
        try:
            async with self._db.db.begin_nested():
                model = await self.create(PromoCodeModel.from_entity(code))
        except IntegrityError as exc:
            raise PromoCodeDuplicateError() from exc
        return model.to_entity()

    async def get_by_code(
        self, code: str, *, for_update: bool = False
    ) -> PromoCode | None:
        statement = select(PromoCodeModel).where(
            PromoCodeModel.code == normalize_promo_code(code)
        )
        if for_update:
            statement = statement.with_for_update().execution_options(
                populate_existing=True
            )
        model = await self._db.scalar(statement)
        return model.to_entity() if model is not None else None

    async def get_code(self, code_id: UUID) -> PromoCode | None:
        model = await self.get(code_id)
        return model.to_entity() if model is not None else None

    async def list_codes(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[PromoCode]:
        models = await self.get_all(limit=limit, offset=offset)
        return [model.to_entity() for model in models]

    async def save(self, code: PromoCode) -> PromoCode:
        model = await self.get(code.id)
        if model is None:
            return await self.create_code(code)
        model.code = code.code
        model.credits = code.credits
        model.max_redemptions = code.max_redemptions
        model.redeemed_count = code.redeemed_count
        model.expires_at = code.expires_at
        model.is_active = code.is_active
        await self._db.flush()
        await self._db.refresh(model)
        return model.to_entity()


class PromoRedemptionRepository(CrudRepository[PromoRedemptionModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, PromoRedemptionModel)

    async def exists(self, promo_code_id: UUID, user_id: UUID) -> bool:
        return (
            await self._db.scalar(
                select(PromoRedemptionModel.id).where(
                    PromoRedemptionModel.promo_code_id == promo_code_id,
                    PromoRedemptionModel.user_id == user_id,
                )
            )
        ) is not None

    async def create_redemption(self, redemption: PromoRedemption) -> PromoRedemption:
        try:
            async with self._db.db.begin_nested():
                model = await self.create(
                    PromoRedemptionModel(
                        id=redemption.id,
                        promo_code_id=redemption.promo_code_id,
                        user_id=redemption.user_id,
                        credits=redemption.credits,
                    )
                )
        except IntegrityError as exc:
            raise PromoCodeAlreadyRedeemedError() from exc
        return replace(redemption, created_at=model.created_at)
