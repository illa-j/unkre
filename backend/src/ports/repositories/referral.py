from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.entities.referral import Referral


class ReferralRepositoryInterface(Protocol):
    async def create_referral(self, referral: Referral) -> Referral: ...

    async def get_by_referred_user(self, user_id: UUID) -> Referral | None: ...

    async def get_by_referred_user_for_update(
        self, user_id: UUID
    ) -> Referral | None: ...

    async def mark_rewarded(
        self, referral_id: UUID, rewarded_at: datetime
    ) -> bool: ...

    async def stats(self, inviter_id: UUID) -> tuple[int, int, int]: ...
