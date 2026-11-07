from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid7

from domain.enums import PaymentProvider, PaymentStatus
from domain.exceptions.payments import InvalidCurrencyError, InvalidPaymentStateError
from domain.validators import NumberValidator, PaymentAmountValidator, TextValidator


@dataclass(frozen=True, kw_only=True)
class Payment:
    wallet_id: UUID
    provider: PaymentProvider
    credits: int
    amount: Decimal
    currency: str
    idempotency_key: str
    id: UUID = field(default_factory=uuid7)
    status: PaymentStatus = PaymentStatus.PENDING
    paid_amount: Decimal | None = None
    provider_invoice_id: str | None = None
    provider_payment_id: str | None = None
    provider_transaction_id: str | None = None
    checkout_url: str | None = None
    telegram_user_id: int | None = None
    asset_code: str | None = None
    blockchain_code: str | None = None
    asset_amount: Decimal | None = None
    asset_fee: Decimal | None = None
    blockchain_hash: str | None = None
    sender_address: str | None = None
    expires_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        NumberValidator.validate_integer(self.credits, min_value=1, max_value=2**63 - 1)
        PaymentAmountValidator.validate(self.amount)
        PaymentAmountValidator.validate(self.paid_amount, nullable=True)
        PaymentAmountValidator.validate(self.asset_amount, nullable=True)
        PaymentAmountValidator.validate(self.asset_fee, allow_zero=True, nullable=True)
        currency = TextValidator.validate(self.currency, min_length=3, max_length=3)
        if not currency.isascii() or not currency.isalpha() or not currency.isupper():
            raise InvalidCurrencyError()
        TextValidator.validate(self.idempotency_key, max_length=255)
        for value in (
            self.provider_invoice_id,
            self.provider_payment_id,
            self.provider_transaction_id,
            self.blockchain_hash,
            self.sender_address,
        ):
            TextValidator.validate(value, max_length=255, nullable=True)
        TextValidator.validate(self.checkout_url, max_length=2048, nullable=True)
        TextValidator.validate(self.asset_code, max_length=32, nullable=True)
        TextValidator.validate(self.blockchain_code, max_length=32, nullable=True)
        if self.asset_fee is not None and (
            self.asset_amount is None or self.asset_fee > self.asset_amount
        ):
            raise InvalidPaymentStateError("asset fee exceeds the received amount")
        if self.asset_amount is not None and (
            self.asset_code is None or self.blockchain_code is None
        ):
            raise InvalidPaymentStateError("asset and blockchain are required")
        if self.provider == PaymentProvider.TELEGRAM_STARS:
            if self.telegram_user_id is not None:
                NumberValidator.validate_integer(
                    self.telegram_user_id, min_value=1, max_value=2**63 - 1
                )
            if self.currency != "XTR" or self.amount != int(self.amount):
                raise InvalidPaymentStateError("Stars require an integer XTR amount")
            if self.paid_amount is not None and self.paid_amount != self.amount:
                raise InvalidPaymentStateError("Stars payment amount does not match")
            if any(
                value is not None
                for value in (
                    self.asset_code,
                    self.blockchain_code,
                    self.asset_amount,
                    self.asset_fee,
                    self.blockchain_hash,
                    self.sender_address,
                )
            ):
                raise InvalidPaymentStateError("Stars cannot contain crypto details")
        elif self.currency == "XTR" or self.telegram_user_id is not None:
            raise InvalidPaymentStateError("crypto payment contains Stars details")
        if self.status in (PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED) and (
            self.paid_at is None
            or self.provider_transaction_id is None
            or self.paid_amount is None
            or self.paid_amount < self.amount
        ):
            raise InvalidPaymentStateError("confirmed payment details are required")


@dataclass(frozen=True, kw_only=True)
class Wallet:
    id: UUID
    user_id: UUID
    credits: int

    def __post_init__(self) -> None:
        NumberValidator.validate_integer(self.credits, min_value=0, max_value=2**63 - 1)


@dataclass(frozen=True, kw_only=True)
class CreditPurchase:
    wallet_id: UUID
    payment_id: UUID
    amount: int
    balance_before: int
    balance_after: int
    idempotency_key: str
    id: UUID = field(default_factory=uuid7)

    def __post_init__(self) -> None:
        NumberValidator.validate_integer(self.amount, min_value=1, max_value=2**63 - 1)
        NumberValidator.validate_integer(
            self.balance_before, min_value=0, max_value=2**63 - 1
        )
        NumberValidator.validate_integer(
            self.balance_after, min_value=0, max_value=2**63 - 1
        )
        TextValidator.validate(self.idempotency_key, max_length=255)
        if self.balance_after - self.balance_before != self.amount:
            raise InvalidPaymentStateError(
                "purchase amount does not match the balance change"
            )
