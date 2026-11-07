from dataclasses import replace
from datetime import datetime
from uuid import UUID

from domain.entities.promo import PromoCode, PromoRedemption
from domain.entities.user import User
from domain.exceptions.auth import UserBlockedError
from domain.exceptions.promo import (
    InvalidPromoCodeError,
    PromoCodeAlreadyRedeemedError,
    PromoCodeDuplicateError,
    PromoCodeExhaustedError,
    PromoCodeExpiredError,
    PromoCodeInactiveError,
    PromoCodeNotFoundError,
)
from domain.validators import NumberValidator
from ports.repositories.payment import (
    TransactionRepositoryInterface,
    WalletRepositoryInterface,
)
from ports.repositories.promo import (
    PromoCodeRepositoryInterface,
    PromoRedemptionRepositoryInterface,
)
from ports.repositories.user import UserRepositoryInterface


class PromoService:
    def __init__(
        self,
        codes: PromoCodeRepositoryInterface,
        redemptions: PromoRedemptionRepositoryInterface,
        users: UserRepositoryInterface,
        wallets: WalletRepositoryInterface,
        transactions: TransactionRepositoryInterface,
    ) -> None:
        self._codes = codes
        self._redemptions = redemptions
        self._users = users
        self._wallets = wallets
        self._transactions = transactions

    async def redeem(self, user_id: UUID, code: str) -> tuple[PromoCode, int]:
        user = await self._users.get_user(user_id)
        if user is None:
            raise PromoCodeNotFoundError()
        self._check_user(user)
        promo = await self._codes.get_by_code(code, for_update=True)
        if promo is None:
            raise PromoCodeNotFoundError()
        self._check_available(promo)
        if await self._redemptions.exists(promo.id, user_id):
            raise PromoCodeAlreadyRedeemedError()
        wallet = await self._wallets.get_by_user(user_id)
        if wallet is None:
            raise PromoCodeNotFoundError()
        redemption = PromoRedemption(
            promo_code_id=promo.id,
            user_id=user_id,
            credits=promo.credits,
        )
        await self._redemptions.create_redemption(redemption)
        await self._codes.save(
            replace(promo, redeemed_count=promo.redeemed_count + 1)
        )
        wallet = await self._transactions.post_adjustment(
            wallet,
            amount=promo.credits,
            idempotency_key=f"promo:{promo.id}:{user_id}",
            description=f"Promo code {promo.code}",
        )
        return promo, wallet.credits

    async def create(
        self,
        code: str,
        credits: int,
        *,
        max_redemptions: int | None = None,
        expires_at: datetime | None = None,
        is_active: bool = True,
    ) -> PromoCode:
        candidate = PromoCode(
            code=code,
            credits=credits,
            max_redemptions=max_redemptions,
            expires_at=expires_at,
            is_active=is_active,
        )
        existing = await self._codes.get_by_code(candidate.code)
        if existing is not None:
            raise PromoCodeDuplicateError()
        return await self._codes.create_code(candidate)

    async def list_codes(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[PromoCode]:
        NumberValidator.validate_integer(limit, min_value=1, max_value=100)
        NumberValidator.validate_integer(offset, min_value=0)
        return await self._codes.list_codes(limit=limit, offset=offset)

    async def set_active(self, code_id: UUID, is_active: bool) -> PromoCode:
        code = await self._codes.get_code(code_id)
        if code is None:
            raise PromoCodeNotFoundError()
        if not isinstance(is_active, bool):
            raise InvalidPromoCodeError("is_active must be a boolean")
        return await self._codes.save(replace(code, is_active=is_active))

    @staticmethod
    def _check_user(user: User) -> None:
        if user.is_blocked:
            raise UserBlockedError("User is blocked")

    @staticmethod
    def _check_available(code: PromoCode) -> None:
        if not code.is_active:
            raise PromoCodeInactiveError()
        if code.is_expired():
            raise PromoCodeExpiredError()
        if code.is_exhausted():
            raise PromoCodeExhaustedError()
