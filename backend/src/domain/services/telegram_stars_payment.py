from dataclasses import replace
from datetime import datetime, timedelta
from logging import getLogger
from uuid import UUID

from aiogram import Bot
from aiogram.types import (
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    TransactionPartnerUser,
)

from domain.entities.payment import Payment
from domain.enums import PaymentProvider, PaymentStatus
from domain.exceptions import ValidationError
from domain.exceptions.auth import UserBlockedError
from domain.exceptions.payments import InvalidPaymentStateError
from domain.services.payment import PaymentService
from domain.services.referral import ReferralService
from domain.validators import NumberValidator, TextValidator
from ports.repositories.payment import (
    PaymentRepositoryInterface,
    TransactionRepositoryInterface,
    WalletRepositoryInterface,
)
from ports.repositories.user import UserRepositoryInterface

logger = getLogger(__name__)


class TelegramStarsPaymentService(PaymentService):
    def __init__(
        self,
        payments: PaymentRepositoryInterface,
        wallets: WalletRepositoryInterface,
        transactions: TransactionRepositoryInterface,
        users: UserRepositoryInterface,
        bot: Bot,
        *,
        invoice_ttl: timedelta = timedelta(hours=1),
        referrals: ReferralService | None = None,
    ) -> None:
        super().__init__(
            payments,
            wallets,
            transactions,
            users,
            PaymentProvider.TELEGRAM_STARS,
            invoice_ttl=invoice_ttl,
            referrals=referrals,
        )
        self._bot = bot

    async def create_invoice(
        self,
        user_id: UUID,
        *,
        credits: int,
        stars: int,
        idempotency_key: str,
        title: str = "Credits",
        description: str = "Top up your credit balance",
    ) -> Payment:
        stars = NumberValidator.validate_integer(
            stars, min_value=1, max_value=2**31 - 1
        )
        title = TextValidator.validate(title, max_length=32)
        description = TextValidator.validate(description, max_length=255)
        payment = await self._prepare_payment(
            user_id,
            credits=credits,
            amount=stars,
            currency="XTR",
            idempotency_key=idempotency_key,
        )
        if payment.checkout_url is not None or payment.status != PaymentStatus.PENDING:
            return payment
        if self._is_expired(payment):
            raise InvalidPaymentStateError("invoice has expired")
        link = await self._bot.create_invoice_link(
            title=title,
            description=description,
            payload=str(payment.id),
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=title, amount=stars)],
        )
        return await self._payments.save(
            replace(payment, checkout_url=self._checkout_url(link))
        )

    async def validate_pre_checkout(self, query: PreCheckoutQuery) -> Payment:
        payment = await self._require_invoice(query.invoice_payload)
        self._check_order(
            payment, query.from_user.id, query.currency, query.total_amount
        )
        if payment.status != PaymentStatus.PENDING or self._is_expired(payment):
            raise InvalidPaymentStateError(
                "invoice is no longer available for checkout"
            )
        wallet = await self._wallets.get_wallet(payment.wallet_id)
        user = (
            await self._users.get_user(wallet.user_id) if wallet is not None else None
        )
        if user is None or user.is_blocked:
            raise UserBlockedError("User is blocked or no longer available")
        if (
            payment.telegram_user_id is not None
            and user.telegram_id != query.from_user.id
        ):
            raise UserBlockedError("Telegram payer does not match the account")
        # Reserve this single-use order; pre-checkout itself never grants credits.
        return await self._payments.save(
            replace(payment, status=PaymentStatus.PROCESSING)
        )

    async def handle_successful_payment(self, message: Message) -> bool:
        # Only pass messages received from an authenticated Telegram update.
        received = message.successful_payment
        if received is None or message.from_user is None:
            raise InvalidPaymentStateError("successful payment and sender are required")
        if (
            received.is_recurring
            or received.is_first_recurring
            or received.subscription_expiration_date is not None
        ):
            raise InvalidPaymentStateError("subscription payments are not supported")
        payment = await self._require_invoice(received.invoice_payload)
        self._check_order(
            payment, message.from_user.id, received.currency, received.total_amount
        )
        return await self._credit_payment(
            payment,
            transaction_id=received.telegram_payment_charge_id,
            paid_amount=received.total_amount,
            paid_at=message.date,
            details={"telegram_user_id": message.from_user.id},
        )

    async def reconcile(self, *, since: datetime, page_size: int = 100) -> int:
        since = self._utc(since)
        NumberValidator.validate_integer(page_size, min_value=1, max_value=100)
        credited = 0
        offset = 0
        while True:
            page = await self._bot.get_star_transactions(offset=offset, limit=page_size)
            for row in page.transactions:
                source = row.source
                if (
                    row.date < since
                    or not isinstance(source, TransactionPartnerUser)
                    or source.transaction_type != "invoice_payment"
                    or source.subscription_period is not None
                    or row.receiver is not None
                    or row.amount <= 0
                    or row.nanostar_amount
                ):
                    continue
                try:
                    ident = UUID(source.invoice_payload)
                except ValueError, TypeError, AttributeError:
                    continue
                try:
                    async with self._payments.settlement_scope():
                        payment = await self._find_payment(ident)
                        if payment is None:
                            continue
                        self._check_order(payment, source.user.id, "XTR", row.amount)
                        applied = await self._credit_payment(
                            payment,
                            transaction_id=row.id,
                            paid_amount=row.amount,
                            paid_at=row.date,
                            details={"telegram_user_id": source.user.id},
                        )
                except ValidationError:
                    logger.exception(
                        "Skipping invalid Stars reconciliation for payment %s", ident
                    )
                else:
                    credited += applied
            if len(page.transactions) < page_size:
                return credited
            offset += len(page.transactions)

    async def _require_invoice(self, payload: str) -> Payment:
        try:
            ident = UUID(payload)
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidPaymentStateError("invalid invoice payload") from exc
        payment = await self._find_payment(ident)
        if payment is None:
            raise InvalidPaymentStateError("invoice not found")
        return payment

    @staticmethod
    def _check_order(
        payment: Payment, telegram_user_id: int, currency: str, amount: int
    ) -> None:
        NumberValidator.validate_integer(telegram_user_id, min_value=1)
        NumberValidator.validate_integer(amount, min_value=1)
        if (
            currency != "XTR"
            or (
                payment.telegram_user_id is not None
                and payment.telegram_user_id != telegram_user_id
            )
            or payment.amount != amount
        ):
            raise InvalidPaymentStateError(
                "Telegram payer, currency or amount does not match"
            )
