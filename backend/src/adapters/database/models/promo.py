from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from adapters.database.models import Base, TimestampMixin
from adapters.database.types import CreditAmount, UUIDPrimaryKey
from domain.entities.promo import PromoCode, PromoRedemption, normalize_promo_code
from domain.validators import NumberValidator

if TYPE_CHECKING:
    from adapters.database.models import UserModel


class PromoCodeModel(TimestampMixin, Base):
    __tablename__ = "promo_codes"

    id: Mapped[UUIDPrimaryKey]
    code: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    credits: Mapped[CreditAmount] = mapped_column(nullable=False)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redeemed_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    redemptions: Mapped[list[PromoRedemptionModel]] = relationship(
        "PromoRedemptionModel",
        back_populates="promo_code",
    )

    __table_args__ = (
        CheckConstraint(
            "length(code) BETWEEN 3 AND 64",
            name="check_promo_codes_code_length",
        ),
        CheckConstraint(
            "credits BETWEEN 1 AND 2147483647",
            name="check_promo_codes_credits_range",
        ),
        CheckConstraint(
            "max_redemptions IS NULL OR max_redemptions BETWEEN 1 AND 2147483647",
            name="check_promo_codes_max_redemptions_range",
        ),
        CheckConstraint(
            "redeemed_count BETWEEN 0 AND 2147483647",
            name="check_promo_codes_redeemed_count_range",
        ),
        CheckConstraint(
            "max_redemptions IS NULL OR redeemed_count <= max_redemptions",
            name="check_promo_codes_redemption_limit",
        ),
    )

    @validates("code")
    def validate_code(self, key: str, value: str) -> str:
        return normalize_promo_code(value)

    @validates("credits")
    def validate_credits(self, key: str, value: int) -> int:
        return NumberValidator.validate_integer(value, min_value=1, max_value=2**31 - 1)

    @validates("max_redemptions")
    def validate_max_redemptions(self, key: str, value: int | None) -> int | None:
        return NumberValidator.validate_integer(
            value, min_value=1, max_value=2**31 - 1, nullable=True
        )

    @validates("redeemed_count")
    def validate_redeemed_count(self, key: str, value: int) -> int:
        return NumberValidator.validate_integer(value, min_value=0, max_value=2**31 - 1)

    @validates("expires_at")
    def validate_expires_at(self, key: str, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise ValueError("the expiry must be a datetime")
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def to_entity(self) -> PromoCode:
        expires_at = self.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return PromoCode(
            id=self.id,
            code=self.code,
            credits=self.credits,
            max_redemptions=self.max_redemptions,
            redeemed_count=self.redeemed_count,
            expires_at=expires_at,
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, code: PromoCode) -> PromoCodeModel:
        return cls(
            id=code.id,
            code=code.code,
            credits=code.credits,
            max_redemptions=code.max_redemptions,
            redeemed_count=code.redeemed_count,
            expires_at=code.expires_at,
            is_active=code.is_active,
        )


class PromoRedemptionModel(TimestampMixin, Base):
    __tablename__ = "promo_redemptions"

    id: Mapped[UUIDPrimaryKey]
    promo_code_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("promo_codes.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    credits: Mapped[CreditAmount] = mapped_column(nullable=False)

    promo_code: Mapped[PromoCodeModel] = relationship(
        "PromoCodeModel", back_populates="redemptions"
    )
    user: Mapped[UserModel] = relationship("UserModel")

    __table_args__ = (
        UniqueConstraint(
            "promo_code_id", "user_id", name="uq_promo_redemptions_code_user"
        ),
        CheckConstraint(
            "credits BETWEEN 1 AND 9223372036854775807",
            name="check_promo_redemptions_credits_range",
        ),
    )

    @validates("credits")
    def validate_credits(self, key: str, value: int) -> int:
        return NumberValidator.validate_integer(value, min_value=1, max_value=2**63 - 1)

    def to_entity(self) -> PromoRedemption:
        return PromoRedemption(
            id=self.id,
            promo_code_id=self.promo_code_id,
            user_id=self.user_id,
            credits=self.credits,
            created_at=self.created_at,
        )
