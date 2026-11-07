from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column, relationship, validates

from adapters.database.models import Base, TimestampMixin
from adapters.database.types import (
    CreditAmount,
    MoneyAmount,
    String255,
    Timestamp,
    UUIDPrimaryKey,
)
from domain.entities.payment import Payment
from domain.enums import PaymentProvider, PaymentStatus
from domain.exceptions import InvalidCurrencyError, InvalidPaymentStateError
from domain.validators import NumberValidator, PaymentAmountValidator, TextValidator

if TYPE_CHECKING:
    from adapters.database.models import (
        PaymentRefundModel,
        TransactionModel,
        WalletModel,
    )


class PaymentModel(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[UUIDPrimaryKey]
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wallets.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        Enum(
            PaymentProvider,
            values_callable=lambda e: [v.value for v in e],
            name="payment_provider",
            create_constraint=True,
        )
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            values_callable=lambda e: [v.value for v in e],
            name="payment_status",
            create_constraint=True,
        ),
        default=PaymentStatus.PENDING,
    )
    credits: Mapped[CreditAmount]
    amount: Mapped[MoneyAmount]
    paid_amount: Mapped[MoneyAmount | None] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    idempotency_key: Mapped[String255] = mapped_column(unique=True)
    provider_invoice_id: Mapped[String255 | None] = mapped_column(nullable=True)
    provider_payment_id: Mapped[String255 | None] = mapped_column(nullable=True)
    provider_transaction_id: Mapped[String255 | None] = mapped_column(nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    asset_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    blockchain_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    asset_amount: Mapped[MoneyAmount | None] = mapped_column(nullable=True)
    asset_fee: Mapped[MoneyAmount | None] = mapped_column(nullable=True)
    blockchain_hash: Mapped[String255 | None] = mapped_column(nullable=True)
    sender_address: Mapped[String255 | None] = mapped_column(nullable=True)
    expires_at: Mapped[Timestamp | None] = mapped_column(nullable=True)
    paid_at: Mapped[Timestamp | None] = mapped_column(nullable=True)

    wallet: Mapped[WalletModel] = relationship("WalletModel", back_populates="payments")
    refund: Mapped[PaymentRefundModel | None] = relationship(
        "PaymentRefundModel",
        back_populates="payment",
        foreign_keys="[PaymentRefundModel.payment_id, PaymentRefundModel.wallet_id]",
        passive_deletes="all",
    )
    transaction: Mapped[TransactionModel | None] = relationship(
        "TransactionModel",
        back_populates="payment",
        foreign_keys="TransactionModel.payment_id",
        passive_deletes="all",
    )

    __table_args__ = (
        UniqueConstraint("id", "wallet_id", name="uq_payments_id_wallet"),
        UniqueConstraint(
            "provider", "provider_invoice_id", name="uq_payments_provider_invoice"
        ),
        UniqueConstraint(
            "provider", "provider_payment_id", name="uq_payments_provider_payment"
        ),
        UniqueConstraint(
            "provider",
            "provider_transaction_id",
            name="uq_payments_provider_transaction",
        ),
        CheckConstraint(
            "credits BETWEEN 1 AND 9223372036854775807",
            name="check_payments_credits_range",
        ),
        CheckConstraint(
            "amount > 0 AND amount <= 99999999999999999999.999999999999999999",
            name="check_payments_amount_range",
        ),
        CheckConstraint(
            "length(currency) = 3 AND substr(currency, 1, 1) BETWEEN 'A' AND 'Z' AND substr(currency, 2, 1) BETWEEN 'A' AND 'Z' AND substr(currency, 3, 1) BETWEEN 'A' AND 'Z'",
            name="check_payments_currency",
        ),
        CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 255 AND length(idempotency_key) <= 255",
            name="check_payments_idempotency_key_length",
        ),
        CheckConstraint(
            "(provider = 'telegram_stars' AND currency = 'XTR' AND amount = round(amount, 0) AND (telegram_user_id IS NULL OR telegram_user_id > 0) AND asset_code IS NULL AND blockchain_code IS NULL AND asset_amount IS NULL AND asset_fee IS NULL AND blockchain_hash IS NULL AND sender_address IS NULL) OR (provider = 'atlos' AND currency <> 'XTR' AND telegram_user_id IS NULL)",
            name="check_payments_provider_details",
        ),
        CheckConstraint(
            "status NOT IN ('succeeded', 'refunded') OR (paid_at IS NOT NULL AND provider_transaction_id IS NOT NULL AND paid_amount IS NOT NULL AND paid_amount >= amount)",
            name="check_payments_success_details",
        ),
        CheckConstraint(
            "paid_amount IS NULL OR (paid_amount > 0 AND paid_amount <= 99999999999999999999.999999999999999999)",
            name="check_payments_paid_amount_range",
        ),
        CheckConstraint(
            "provider <> 'telegram_stars' OR paid_amount IS NULL OR paid_amount = amount",
            name="check_payments_stars_paid_amount",
        ),
        CheckConstraint(
            "asset_amount IS NULL OR (asset_amount > 0 AND asset_amount <= 99999999999999999999.999999999999999999)",
            name="check_payments_asset_amount_range",
        ),
        CheckConstraint(
            "asset_fee IS NULL OR (asset_fee BETWEEN 0 AND 99999999999999999999.999999999999999999)",
            name="check_payments_asset_fee_range",
        ),
        CheckConstraint(
            "asset_fee IS NULL OR (asset_amount IS NOT NULL AND asset_fee <= asset_amount)",
            name="check_payments_asset_fee_limit",
        ),
        CheckConstraint(
            "asset_amount IS NULL OR (asset_code IS NOT NULL AND blockchain_code IS NOT NULL)",
            name="check_payments_asset_details",
        ),
        CheckConstraint(
            "provider_invoice_id IS NULL OR length(provider_invoice_id) BETWEEN 1 AND 255",
            name="check_payments_invoice_id_length",
        ),
        CheckConstraint(
            "provider_payment_id IS NULL OR length(provider_payment_id) BETWEEN 1 AND 255",
            name="check_payments_payment_id_length",
        ),
        CheckConstraint(
            "provider_transaction_id IS NULL OR length(provider_transaction_id) BETWEEN 1 AND 255",
            name="check_payments_transaction_id_length",
        ),
        CheckConstraint(
            "checkout_url IS NULL OR length(checkout_url) BETWEEN 1 AND 2048",
            name="check_payments_checkout_url_length",
        ),
        CheckConstraint(
            "asset_code IS NULL OR length(asset_code) BETWEEN 1 AND 32",
            name="check_payments_asset_code_length",
        ),
        CheckConstraint(
            "blockchain_code IS NULL OR length(blockchain_code) BETWEEN 1 AND 32",
            name="check_payments_blockchain_code_length",
        ),
        CheckConstraint(
            "blockchain_hash IS NULL OR length(blockchain_hash) BETWEEN 1 AND 255",
            name="check_payments_blockchain_hash_length",
        ),
        CheckConstraint(
            "sender_address IS NULL OR length(sender_address) BETWEEN 1 AND 255",
            name="check_payments_sender_address_length",
        ),
    )

    @validates("credits")
    def validate_credits(self, key: str, value: int) -> int:
        return NumberValidator.validate_integer(value, min_value=1, max_value=2**63 - 1)

    @validates("amount")
    def validate_amount(self, key: str, value: Decimal) -> Decimal:
        return PaymentAmountValidator.validate(value)

    @validates("paid_amount")
    def validate_paid_amount(self, key: str, value: Decimal | None) -> Decimal | None:
        return PaymentAmountValidator.validate(value, nullable=True)

    @validates("asset_amount", "asset_fee")
    def validate_optional_amount(
        self, key: str, value: Decimal | None
    ) -> Decimal | None:
        return PaymentAmountValidator.validate(
            value, allow_zero=key == "asset_fee", nullable=True
        )

    @validates("currency")
    def validate_currency(self, key: str, value: str) -> str:
        value = TextValidator.validate(value, min_length=3, max_length=3)
        if not value.isascii() or not value.isalpha() or not value.isupper():
            raise InvalidCurrencyError()
        return value

    @validates("idempotency_key")
    def validate_idempotency_key(self, key: str, value: str) -> str:
        return TextValidator.validate(value, max_length=255, strip=True)

    @validates(
        "provider_invoice_id",
        "provider_payment_id",
        "provider_transaction_id",
        "blockchain_hash",
        "sender_address",
    )
    def validate_optional_identifier(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(value, max_length=255, strip=True, nullable=True)

    @validates("asset_code", "blockchain_code")
    def validate_asset_code(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(value, max_length=32, strip=True, nullable=True)

    @validates("checkout_url")
    def validate_checkout_url(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(value, max_length=2048, strip=True, nullable=True)

    @validates("telegram_user_id")
    def validate_telegram_user_id(self, key: str, value: int | None) -> int | None:
        return NumberValidator.validate_integer(
            value, min_value=1, max_value=2**63 - 1, nullable=True
        )

    def to_entity(self) -> Payment:
        return Payment(
            id=self.id,
            wallet_id=self.wallet_id,
            provider=self.provider,
            credits=self.credits,
            amount=self.amount,
            currency=self.currency,
            idempotency_key=self.idempotency_key,
            status=self.status,
            paid_amount=self.paid_amount,
            provider_invoice_id=self.provider_invoice_id,
            provider_payment_id=self.provider_payment_id,
            provider_transaction_id=self.provider_transaction_id,
            checkout_url=self.checkout_url,
            telegram_user_id=self.telegram_user_id,
            asset_code=self.asset_code,
            blockchain_code=self.blockchain_code,
            asset_amount=self.asset_amount,
            asset_fee=self.asset_fee,
            blockchain_hash=self.blockchain_hash,
            sender_address=self.sender_address,
            expires_at=self.expires_at,
            paid_at=self.paid_at,
            created_at=self.created_at,
        )


@event.listens_for(PaymentModel, "before_update")
def protect_payment_snapshot(
    mapper: Mapper[PaymentModel], connection: Connection, target: PaymentModel
) -> None:
    state = inspect(target)
    for field in (
        "wallet_id",
        "provider",
        "credits",
        "amount",
        "currency",
        "idempotency_key",
    ):
        if state.attrs[field].history.has_changes():
            raise InvalidPaymentStateError(
                f"payment field '{field}' cannot be changed after creation"
            )
    payer = state.attrs.telegram_user_id.history
    if payer.has_changes() and not (
        payer.deleted == [None]
        and target.telegram_user_id is not None
        and target.provider == PaymentProvider.TELEGRAM_STARS
        and target.status == PaymentStatus.SUCCEEDED
    ):
        raise InvalidPaymentStateError(
            "Telegram payer can only be captured once on successful payment"
        )
