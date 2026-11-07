from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import (
    Mapped,
    Mapper,
    Session,
    mapped_column,
    relationship,
    validates,
)

from adapters.database.models import (
    Base,
    PaymentModel,
    PaymentRefundModel,
    TimestampMixin,
)
from adapters.database.types import CreditAmount, String255, String4096, UUIDPrimaryKey
from domain.enums import PaymentRefundStatus, PaymentStatus, TransactionType
from domain.exceptions import (
    ImmutableTransactionError,
    InvalidPaymentStateError,
)
from domain.validators import NumberValidator, TextValidator

if TYPE_CHECKING:
    from adapters.database.models import GenerationModel, WalletModel


class TransactionModel(TimestampMixin, Base):
    __tablename__ = "transactions"

    id: Mapped[UUIDPrimaryKey]
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wallets.id", ondelete="RESTRICT"), index=True
    )
    type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            values_callable=lambda e: [v.value for v in e],
            name="transaction_type",
            create_constraint=True,
        )
    )
    amount: Mapped[CreditAmount]
    balance_before: Mapped[CreditAmount]
    balance_after: Mapped[CreditAmount]
    idempotency_key: Mapped[String255]
    description: Mapped[String4096 | None] = mapped_column(nullable=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(unique=True, nullable=True)
    payment_refund_id: Mapped[uuid.UUID | None] = mapped_column(
        unique=True, nullable=True
    )
    generation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("generations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    reverses_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        unique=True, nullable=True
    )

    wallet: Mapped[WalletModel] = relationship(
        "WalletModel", back_populates="transactions", foreign_keys=[wallet_id]
    )
    payment: Mapped[PaymentModel | None] = relationship(
        "PaymentModel", back_populates="transaction", foreign_keys=[payment_id]
    )
    payment_refund: Mapped[PaymentRefundModel | None] = relationship(
        "PaymentRefundModel",
        back_populates="transaction",
        foreign_keys=[payment_refund_id],
    )
    generation: Mapped[GenerationModel | None] = relationship("GenerationModel")
    reverses_transaction: Mapped[TransactionModel | None] = relationship(
        "TransactionModel",
        remote_side="TransactionModel.id",
        foreign_keys=[reverses_transaction_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "wallet_id", "idempotency_key", name="uq_transactions_wallet_idempotency"
        ),
        UniqueConstraint("id", "wallet_id", name="uq_transactions_id_wallet"),
        ForeignKeyConstraint(
            ["payment_id", "wallet_id"],
            ["payments.id", "payments.wallet_id"],
            ondelete="RESTRICT",
            name="fk_transactions_payment_wallet",
        ),
        ForeignKeyConstraint(
            ["payment_refund_id", "wallet_id"],
            ["payment_refunds.id", "payment_refunds.wallet_id"],
            ondelete="RESTRICT",
            name="fk_transactions_refund_wallet",
        ),
        ForeignKeyConstraint(
            ["reverses_transaction_id", "wallet_id"],
            ["transactions.id", "transactions.wallet_id"],
            ondelete="RESTRICT",
            name="fk_transactions_reversal_wallet",
        ),
        CheckConstraint(
            "amount <> 0 AND amount BETWEEN -9223372036854775807 AND 9223372036854775807",
            name="check_transactions_amount_range",
        ),
        CheckConstraint(
            "balance_before BETWEEN 0 AND 9223372036854775807 AND balance_after BETWEEN 0 AND 9223372036854775807",
            name="check_transactions_balances_range",
        ),
        CheckConstraint(
            "balance_after - balance_before = amount",
            name="check_transactions_balance_delta",
        ),
        CheckConstraint(
            "length(trim(idempotency_key)) BETWEEN 1 AND 255 AND length(idempotency_key) <= 255",
            name="check_transactions_idempotency_key_length",
        ),
        CheckConstraint(
            "description IS NULL OR length(description) <= 4096",
            name="check_transactions_description_length",
        ),
        CheckConstraint(
            "(type = 'purchase' AND amount > 0 AND payment_id IS NOT NULL AND payment_refund_id IS NULL AND reverses_transaction_id IS NULL) OR (type = 'spend' AND amount < 0 AND payment_id IS NULL AND payment_refund_id IS NULL AND reverses_transaction_id IS NULL) OR (type = 'reversal' AND amount > 0 AND reverses_transaction_id IS NOT NULL AND payment_id IS NULL AND payment_refund_id IS NULL) OR (type = 'refund' AND amount < 0 AND payment_refund_id IS NOT NULL AND payment_id IS NULL AND reverses_transaction_id IS NULL) OR (type = 'adjustment' AND payment_id IS NULL AND payment_refund_id IS NULL AND reverses_transaction_id IS NULL)",
            name="check_transactions_type_details",
        ),
        CheckConstraint(
            "reverses_transaction_id IS NULL OR reverses_transaction_id <> id",
            name="check_transactions_not_self_reversal",
        ),
    )

    @validates("amount")
    def validate_amount(self, key: str, value: int) -> int:
        value = NumberValidator.validate_integer(
            value, min_value=-(2**63 - 1), max_value=2**63 - 1
        )
        if value == 0:
            raise InvalidPaymentStateError("transaction amount cannot be zero")
        return value

    @validates("balance_before", "balance_after")
    def validate_balance(self, key: str, value: int) -> int:
        return NumberValidator.validate_integer(value, min_value=0, max_value=2**63 - 1)

    @validates("idempotency_key")
    def validate_idempotency_key(self, key: str, value: str) -> str:
        return TextValidator.validate(value, max_length=255, strip=True)

    @validates("description")
    def validate_description(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(
            value, min_length=0, max_length=4096, nullable=True
        )


@event.listens_for(TransactionModel, "before_update")
@event.listens_for(TransactionModel, "before_delete")
def prevent_transaction_mutation(
    mapper: Mapper[TransactionModel], connection: Connection, target: TransactionModel
) -> None:
    state = inspect(target)
    if (state.session is not None and target in state.session.deleted) or any(
        state.attrs[column.key].history.has_changes() for column in mapper.column_attrs
    ):
        raise ImmutableTransactionError()


@event.listens_for(Session, "before_flush")
def validate_transaction_source(
    session: Session, flush_context: object, instances: object
) -> None:
    for row in session.new:
        if not isinstance(row, TransactionModel):
            continue
        if row.type == TransactionType.PURCHASE:
            payment = row.payment
            if payment is None and row.payment_id is not None:
                payment = session.get(PaymentModel, row.payment_id)
            if payment is None or payment.status != PaymentStatus.SUCCEEDED:
                raise InvalidPaymentStateError(
                    "credits can only be purchased with a successful payment"
                )
            if row.amount != payment.credits:
                raise InvalidPaymentStateError(
                    "purchased credits must match the payment"
                )
        elif row.type == TransactionType.REFUND:
            refund = row.payment_refund
            if refund is None and row.payment_refund_id is not None:
                refund = session.get(PaymentRefundModel, row.payment_refund_id)
            if refund is None or refund.status in (
                PaymentRefundStatus.FAILED,
                PaymentRefundStatus.CANCELLED,
            ):
                raise InvalidPaymentStateError(
                    "a credit debit requires an active or successful payment refund"
                )
            if row.amount != -refund.credits:
                raise InvalidPaymentStateError(
                    "refunded credits must match the full payment"
                )
        elif row.type == TransactionType.REVERSAL:
            original = row.reverses_transaction
            if original is None and row.reverses_transaction_id is not None:
                original = session.get(TransactionModel, row.reverses_transaction_id)
            if (
                original is None
                or original is row
                or original.type != TransactionType.SPEND
                or row.amount != -original.amount
            ):
                raise InvalidPaymentStateError(
                    "a reversal must restore the exact amount of a spend transaction"
                )
