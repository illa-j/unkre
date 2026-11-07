from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKeyConstraint,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship, validates

from adapters.database.models import Base, PaymentModel, TimestampMixin
from adapters.database.types import (
    MoneyAmount,
    String255,
    String4096,
    Timestamp,
    UUIDPrimaryKey,
)
from domain.enums import PaymentProvider, PaymentRefundStatus, PaymentStatus
from domain.exceptions import InvalidPaymentStateError
from domain.validators import PaymentAmountValidator, TextValidator

if TYPE_CHECKING:
    from adapters.database.models import TransactionModel


class PaymentRefundModel(TimestampMixin, Base):
    __tablename__ = "payment_refunds"

    id: Mapped[UUIDPrimaryKey]
    payment_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    wallet_id: Mapped[uuid.UUID] = mapped_column(index=True)
    status: Mapped[PaymentRefundStatus] = mapped_column(
        Enum(
            PaymentRefundStatus,
            values_callable=lambda e: [v.value for v in e],
            name="payment_refund_status",
            create_constraint=True,
        ),
        default=PaymentRefundStatus.PENDING,
    )
    idempotency_key: Mapped[String255] = mapped_column(unique=True)
    reason: Mapped[String4096]
    error: Mapped[String4096 | None] = mapped_column(nullable=True)
    atlos_payout_invoice_id: Mapped[String255 | None] = mapped_column(
        unique=True, nullable=True
    )
    recipient_address: Mapped[String255 | None] = mapped_column(nullable=True)
    blockchain_hash: Mapped[String255 | None] = mapped_column(nullable=True)
    asset_amount: Mapped[MoneyAmount | None] = mapped_column(nullable=True)
    asset_fee: Mapped[MoneyAmount | None] = mapped_column(nullable=True)
    completed_at: Mapped[Timestamp | None] = mapped_column(nullable=True)

    payment: Mapped[PaymentModel] = relationship(
        "PaymentModel", back_populates="refund", foreign_keys=[payment_id, wallet_id]
    )
    transaction: Mapped[TransactionModel | None] = relationship(
        "TransactionModel",
        back_populates="payment_refund",
        foreign_keys="TransactionModel.payment_refund_id",
        passive_deletes="all",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["payment_id", "wallet_id"],
            ["payments.id", "payments.wallet_id"],
            ondelete="RESTRICT",
            name="fk_payment_refunds_payment_wallet",
        ),
        UniqueConstraint("id", "wallet_id", name="uq_payment_refunds_id_wallet"),
        CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 255 AND length(idempotency_key) <= 255",
            name="check_payment_refunds_idempotency_key_length",
        ),
        CheckConstraint(
            "length(trim(reason)) BETWEEN 1 AND 4096 AND length(reason) <= 4096",
            name="check_payment_refunds_reason_length",
        ),
        CheckConstraint(
            "error IS NULL OR length(error) <= 4096",
            name="check_payment_refunds_error_length",
        ),
        CheckConstraint(
            "atlos_payout_invoice_id IS NULL OR length(atlos_payout_invoice_id) BETWEEN 1 AND 255",
            name="check_payment_refunds_atlos_invoice_length",
        ),
        CheckConstraint(
            "recipient_address IS NULL OR length(recipient_address) BETWEEN 1 AND 255",
            name="check_payment_refunds_recipient_address_length",
        ),
        CheckConstraint(
            "blockchain_hash IS NULL OR length(blockchain_hash) BETWEEN 1 AND 255",
            name="check_payment_refunds_blockchain_hash_length",
        ),
        CheckConstraint(
            "asset_amount IS NULL OR (asset_amount > 0 AND asset_amount <= 99999999999999999999.999999999999999999)",
            name="check_payment_refunds_asset_amount_range",
        ),
        CheckConstraint(
            "asset_fee IS NULL OR asset_fee BETWEEN 0 AND 99999999999999999999.999999999999999999",
            name="check_payment_refunds_asset_fee_range",
        ),
        CheckConstraint(
            "status <> 'succeeded' OR completed_at IS NOT NULL",
            name="check_payment_refunds_completion",
        ),
    )

    @validates("idempotency_key")
    def validate_idempotency_key(self, key: str, value: str) -> str:
        return TextValidator.validate(value, max_length=255, strip=True)

    @validates("reason")
    def validate_reason(self, key: str, value: str) -> str:
        return TextValidator.validate(value, max_length=4096, strip=True)

    @validates("error")
    def validate_error(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(
            value, min_length=0, max_length=4096, nullable=True
        )

    @validates("atlos_payout_invoice_id", "recipient_address", "blockchain_hash")
    def validate_optional_identifier(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(value, max_length=255, strip=True, nullable=True)

    @validates("asset_amount", "asset_fee")
    def validate_optional_amount(
        self, key: str, value: Decimal | None
    ) -> Decimal | None:
        return PaymentAmountValidator.validate(
            value, allow_zero=key == "asset_fee", nullable=True
        )

    @property
    def amount(self) -> Decimal:
        return (
            self.payment.paid_amount
            if self.payment.paid_amount is not None
            else self.payment.amount
        )

    @property
    def credits(self) -> int:
        return self.payment.credits

    @property
    def currency(self) -> str:
        return self.payment.currency


@event.listens_for(Session, "before_flush")
def validate_refund_source(
    session: Session, flush_context: object, instances: object
) -> None:
    for refund in session.new | session.dirty:
        if not isinstance(refund, PaymentRefundModel) or refund in session.deleted:
            continue
        payment = refund.payment
        if payment is None and refund.payment_id is not None:
            payment = session.get(PaymentModel, refund.payment_id)
        if payment is None or payment.status not in (
            PaymentStatus.SUCCEEDED,
            PaymentStatus.REFUNDED,
        ):
            raise InvalidPaymentStateError("only a successful payment can be refunded")
        if (
            payment.status == PaymentStatus.REFUNDED
            and refund.status != PaymentRefundStatus.SUCCEEDED
        ):
            raise InvalidPaymentStateError(
                "a refunded payment requires a successful refund"
            )
        if payment.provider == PaymentProvider.TELEGRAM_STARS and any(
            value is not None
            for value in (
                refund.atlos_payout_invoice_id,
                refund.recipient_address,
                refund.blockchain_hash,
                refund.asset_amount,
                refund.asset_fee,
            )
        ):
            raise InvalidPaymentStateError(
                "Telegram Stars refunds cannot contain crypto payout details"
            )
        if (
            payment.provider == PaymentProvider.ATLOS
            and refund.status == PaymentRefundStatus.SUCCEEDED
            and any(
                value is None
                for value in (
                    refund.atlos_payout_invoice_id,
                    refund.recipient_address,
                    refund.blockchain_hash,
                    refund.asset_amount,
                )
            )
        ):
            raise InvalidPaymentStateError(
                "successful ATLOS refunds require payout invoice, recipient, blockchain hash and asset amount"
            )
