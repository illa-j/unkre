from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from domain.entities.payment import CreditPurchase, Payment, Wallet
from domain.enums import PaymentProvider


class PaymentRepositoryInterface(Protocol):
    # Isolate one settlement, including referral rewards, without committing.
    def settlement_scope(self) -> AbstractAsyncContextManager[None]: ...

    async def get_for_user(
        self, user_id: UUID, payment_id: UUID, provider: PaymentProvider
    ) -> Payment | None: ...

    async def list_for_user(
        self, user_id: UUID, provider: PaymentProvider, *, limit: int, offset: int
    ) -> list[Payment]: ...

    async def get_for_update(
        self, payment_id: UUID, provider: PaymentProvider
    ) -> Payment | None: ...

    # Return the existing locked order when the idempotency key already exists.
    async def create_or_get(self, payment: Payment) -> Payment: ...

    async def save(self, payment: Payment) -> Payment: ...


class WalletRepositoryInterface(Protocol):
    async def get_wallet(self, wallet_id: UUID) -> Wallet | None: ...

    async def get_by_user(self, user_id: UUID) -> Wallet | None: ...

    async def get_for_update(self, wallet_id: UUID) -> Wallet | None: ...


class TransactionRepositoryInterface(Protocol):
    # Persist all three changes atomically in the caller's transaction.
    async def post_purchase(
        self, payment: Payment, wallet: Wallet, purchase: CreditPurchase
    ) -> None: ...

    async def post_adjustment(
        self,
        wallet: Wallet,
        *,
        amount: int,
        idempotency_key: str,
        description: str | None = None,
    ) -> Wallet: ...

    async def post_spend(
        self,
        wallet: Wallet,
        *,
        amount: int,
        generation_id: UUID,
        idempotency_key: str,
        description: str | None = None,
    ) -> Wallet: ...
