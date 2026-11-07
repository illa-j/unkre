from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update

from adapters.database.models import ReferralModel
from adapters.database.repositiries import CrudRepository
from domain.entities.referral import Referral
from ports import DatabaseManagerInterface


class ReferralRepository(CrudRepository[ReferralModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, ReferralModel)

    async def create_referral(self, referral: Referral) -> Referral:
        model = ReferralModel(
            id=referral.id,
            inviter_id=referral.inviter_id,
            referred_user_id=referral.referred_user_id,
            inviter_credits=referral.inviter_credits,
            invitee_credits=referral.invitee_credits,
            rewarded_at=referral.rewarded_at,
        )
        await self.create(model)
        return model.to_entity()

    async def get_by_referred_user(self, user_id: UUID) -> Referral | None:
        model = await self._db.scalar(
            select(ReferralModel).where(ReferralModel.referred_user_id == user_id)
        )
        return model.to_entity() if model is not None else None

    async def get_by_referred_user_for_update(
        self, user_id: UUID
    ) -> Referral | None:
        model = await self._db.scalar(
            select(ReferralModel)
            .where(ReferralModel.referred_user_id == user_id)
            .with_for_update()
        )
        return model.to_entity() if model is not None else None

    async def mark_rewarded(self, referral_id: UUID, rewarded_at: datetime) -> bool:
        reward = await self._db.scalar(
            update(ReferralModel)
            .where(
                ReferralModel.id == referral_id,
                ReferralModel.rewarded_at.is_(None),
            )
            .values(rewarded_at=rewarded_at)
            .returning(ReferralModel.id)
            .execution_options(synchronize_session=False)
        )
        return reward is not None

    async def stats(self, inviter_id: UUID) -> tuple[int, int, int]:
        count, pending, credits = (
            await self._db.execute(
                select(
                    func.count(ReferralModel.id),
                    func.count(ReferralModel.id).filter(
                        ReferralModel.rewarded_at.is_(None)
                    ),
                    func.coalesce(
                        func.sum(ReferralModel.inviter_credits).filter(
                            ReferralModel.rewarded_at.is_not(None)
                        ),
                        0,
                    ),
                ).where(ReferralModel.inviter_id == inviter_id)
            )
        ).one()
        return int(count), int(pending), int(credits)
