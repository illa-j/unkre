from typing import Protocol
from uuid import UUID

from domain.entities.promo import PromoCode, PromoRedemption


class PromoCodeRepositoryInterface(Protocol):
    async def create_code(self, code: PromoCode) -> PromoCode: ...

    async def get_by_code(
        self, code: str, *, for_update: bool = False
    ) -> PromoCode | None: ...

    async def get_code(self, code_id: UUID) -> PromoCode | None: ...

    async def list_codes(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[PromoCode]: ...

    async def save(self, code: PromoCode) -> PromoCode: ...


class PromoRedemptionRepositoryInterface(Protocol):
    async def exists(self, promo_code_id: UUID, user_id: UUID) -> bool: ...

    async def create_redemption(
        self, redemption: PromoRedemption
    ) -> PromoRedemption: ...
