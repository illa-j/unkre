from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adapters.database.models import Base, TimestampMixin
from adapters.database.types import CreditAmount, Timestamp, UUIDPrimaryKey
from domain.entities.referral import Referral

if TYPE_CHECKING:
    from adapters.database.models import UserModel


class ReferralModel(TimestampMixin, Base):
    __tablename__ = "referrals"

    id: Mapped[UUIDPrimaryKey]
    inviter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    referred_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    inviter_credits: Mapped[CreditAmount] = mapped_column(default=0, nullable=False)
    invitee_credits: Mapped[CreditAmount] = mapped_column(default=0, nullable=False)
    rewarded_at: Mapped[Timestamp | None] = mapped_column(nullable=True)

    inviter: Mapped[UserModel] = relationship(
        "UserModel", foreign_keys=[inviter_id]
    )
    referred_user: Mapped[UserModel] = relationship(
        "UserModel", foreign_keys=[referred_user_id]
    )

    __table_args__ = (
        CheckConstraint(
            "inviter_id <> referred_user_id",
            name="check_referrals_distinct_users",
        ),
        CheckConstraint(
            "inviter_credits BETWEEN 0 AND 9223372036854775807",
            name="check_referrals_inviter_credits_range",
        ),
        CheckConstraint(
            "invitee_credits BETWEEN 0 AND 9223372036854775807",
            name="check_referrals_invitee_credits_range",
        ),
        CheckConstraint(
            "inviter_credits > 0 OR invitee_credits > 0",
            name="check_referrals_has_reward",
        ),
    )

    def to_entity(self) -> Referral:
        return Referral(
            id=self.id,
            inviter_id=self.inviter_id,
            referred_user_id=self.referred_user_id,
            inviter_credits=self.inviter_credits,
            invitee_credits=self.invitee_credits,
            rewarded_at=self.rewarded_at,
            created_at=self.created_at,
        )

