from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from adapters.database.models import Base, TimestampMixin
from adapters.database.types import CreditAmount, UUIDPrimaryKey
from domain.validators import NumberValidator

if TYPE_CHECKING:
    from adapters.database.models import PaymentModel, TransactionModel, UserModel


class WalletModel(TimestampMixin, Base):
    __tablename__ = "wallets"

    id: Mapped[UUIDPrimaryKey]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    credits: Mapped[CreditAmount] = mapped_column(default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    user: Mapped[UserModel] = relationship("UserModel", back_populates="wallet")
    transactions: Mapped[list[TransactionModel]] = relationship(
        "TransactionModel",
        back_populates="wallet",
        foreign_keys="TransactionModel.wallet_id",
        passive_deletes="all",
    )
    payments: Mapped[list[PaymentModel]] = relationship(
        "PaymentModel", back_populates="wallet", passive_deletes="all"
    )

    __mapper_args__ = {"version_id_col": version}

    __table_args__ = (
        CheckConstraint(
            "credits BETWEEN 0 AND 9223372036854775807",
            name="check_wallets_credits_range",
        ),
        CheckConstraint(
            "version BETWEEN 1 AND 2147483647", name="check_wallets_version_range"
        ),
    )

    @validates("credits")
    def validate_credits(self, key: str, value: int) -> int:
        return NumberValidator.validate_integer(value, min_value=0, max_value=2**63 - 1)

    @validates("version")
    def validate_version(self, key: str, value: int) -> int:
        return NumberValidator.validate_integer(value, min_value=1, max_value=2**31 - 1)
