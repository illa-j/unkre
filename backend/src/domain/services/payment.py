from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from domain.entities.payment import CreditPurchase, Payment
from domain.enums import PaymentProvider, PaymentStatus
from domain.exceptions.auth import UserBlockedError
from domain.exceptions.payments import (
    InvalidPaymentStateError,
    PaymentNotFoundError,
    PaymentProviderError,
)
from domain.services.referral import ReferralService
from domain.validators import NumberValidator, PaymentAmountValidator, TextValidator
from ports.repositories.payment import (
    PaymentRepositoryInterface,
    TransactionRepositoryInterface,
    WalletRepositoryInterface,
)
from ports.repositories.user import UserRepositoryInterface


class PaymentService:
    def __init__(
        self,
        payments: PaymentRepositoryInterface,
        wallets: WalletRepositoryInterface,
        transactions: TransactionRepositoryInterface,
        users: UserRepositoryInterface,
        provider: PaymentProvider,
        *,
        invoice_ttl: timedelta = timedelta(hours=1),
        referrals: ReferralService | None = None,
    ) -> None:
        if not isinstance(invoice_ttl, timedelta) or invoice_ttl < timedelta(seconds=1):
            raise ValueError("Invoice TTL must be at least one second")
        self._payments = payments
        self._wallets = wallets
        self._transactions = transactions
        self._users = users
        self._provider = provider
        self._invoice_ttl = invoice_ttl
        self._referrals = referrals

    async def get_payment(self, user_id: UUID, payment_id: UUID) -> Payment:
        payment = await self._payments.get_for_user(user_id, payment_id, self._provider)
        if payment is None:
            raise PaymentNotFoundError()
        return payment

    async def get_payments(
        self, user_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Payment]:
        NumberValidator.validate_integer(limit, min_value=1, max_value=100)
        NumberValidator.validate_integer(offset, min_value=0)
        return await self._payments.list_for_user(
            user_id, self._provider, limit=limit, offset=offset
        )

    async def _prepare_payment(
        self,
        user_id: UUID,
        *,
        credits: int,
        amount: Decimal | int,
        currency: str,
        idempotency_key: str,
    ) -> Payment:
        # Prices and credits come from the application's trusted pricing.
        credits = NumberValidator.validate_integer(
            credits, min_value=1, max_value=2**63 - 1
        )
        amount = PaymentAmountValidator.validate(amount)
        idempotency_key = TextValidator.validate(
            idempotency_key, max_length=255, strip=True
        )
        user = await self._users.get_user(user_id)
        if user is None:
            raise InvalidPaymentStateError("user not found")
        if user.is_blocked:
            raise UserBlockedError("User is blocked")
        wallet = await self._wallets.get_by_user(user_id)
        if wallet is None:
            raise InvalidPaymentStateError("user has no wallet")
        telegram_id = (
            user.telegram_id
            if self._provider == PaymentProvider.TELEGRAM_STARS
            else None
        )
        candidate = Payment(
            wallet_id=wallet.id,
            provider=self._provider,
            credits=credits,
            amount=amount,
            currency=currency,
            idempotency_key=idempotency_key,
            telegram_user_id=telegram_id,
            expires_at=datetime.now(UTC) + self._invoice_ttl,
        )
        payment = await self._payments.create_or_get(candidate)
        # Payer identity belongs to the stored invoice: linking/unlinking Telegram
        # later, or capturing an unlinked payer at settlement, does not change it.
        if (
            payment.wallet_id != wallet.id
            or payment.provider != self._provider
            or payment.credits != credits
            or payment.amount != amount
            or payment.currency != currency
        ):
            raise InvalidPaymentStateError("idempotency key belongs to another order")
        return payment

    async def _find_payment(self, payment_id: UUID) -> Payment | None:
        return await self._payments.get_for_update(payment_id, self._provider)

    async def _credit_payment(
        self,
        payment: Payment,
        *,
        transaction_id: str,
        paid_amount: Decimal | int,
        paid_at: datetime,
        details: dict[str, Any] | None = None,
    ) -> bool:
        transaction_id = TextValidator.validate(transaction_id, max_length=255)
        paid_amount = PaymentAmountValidator.validate(paid_amount)
        paid_at = self._utc(paid_at)
        if paid_amount < payment.amount:
            raise InvalidPaymentStateError(
                "received amount is less than the order amount"
            )
        if payment.status in (PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED):
            if (
                payment.provider_transaction_id != transaction_id
                or payment.paid_amount != paid_amount
            ):
                raise InvalidPaymentStateError("order already has a different payment")
            return False
        wallet = await self._wallets.get_for_update(payment.wallet_id)
        if wallet is None:
            raise InvalidPaymentStateError("wallet not found")
        before = wallet.credits
        after = NumberValidator.validate_integer(
            before + payment.credits, min_value=0, max_value=2**63 - 1
        )
        confirmed = replace(
            payment,
            paid_amount=paid_amount,
            paid_at=paid_at,
            provider_transaction_id=transaction_id,
            status=PaymentStatus.SUCCEEDED,
            **(details or {}),
        )
        purchase = CreditPurchase(
            wallet_id=wallet.id,
            payment_id=payment.id,
            amount=payment.credits,
            balance_before=before,
            balance_after=after,
            idempotency_key=f"payment:{payment.id}",
        )
        await self._transactions.post_purchase(
            confirmed, replace(wallet, credits=after), purchase
        )
        if self._referrals is not None:
            await self._referrals.reward_for_purchase(wallet.user_id)
        return True

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise InvalidPaymentStateError("a timezone-aware timestamp is required")
        return value.astimezone(UTC)

    @staticmethod
    def _is_expired(payment: Payment) -> bool:
        deadline = payment.expires_at
        if deadline is None:
            return False
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        return deadline <= datetime.now(UTC)

    @staticmethod
    def _checkout_url(value: object) -> str:
        value = TextValidator.validate(value, max_length=2048)
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise PaymentProviderError("Provider returned an invalid checkout URL")
        return value
