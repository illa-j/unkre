from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid7

from domain.exceptions.referral import InvalidReferralError
from domain.validators import NumberValidator


@dataclass(frozen=True, kw_only=True)
class Referral:
    inviter_id: UUID
    referred_user_id: UUID
    inviter_credits: int
    invitee_credits: int
    id: UUID = field(default_factory=uuid7)
    rewarded_at: datetime | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.inviter_id, UUID) or not isinstance(
            self.referred_user_id, UUID
        ):
            raise InvalidReferralError("user ids must be UUIDs")
        if self.inviter_id == self.referred_user_id:
            raise InvalidReferralError("a user cannot refer themselves")
        NumberValidator.validate_integer(
            self.inviter_credits, min_value=0, max_value=2**63 - 1
        )
        NumberValidator.validate_integer(
            self.invitee_credits, min_value=0, max_value=2**63 - 1
        )


@dataclass(frozen=True, kw_only=True)
class ReferralStats:
    referral_code: str
    invited_count: int
    credits_earned: int
    referrer_credits: int
    invitee_credits: int
    pending_count: int = 0

    def __post_init__(self) -> None:
        NumberValidator.validate_integer(
            self.invited_count, min_value=0, max_value=2**63 - 1
        )
        for value in (
            self.credits_earned,
            self.pending_count,
            self.referrer_credits,
            self.invitee_credits,
        ):
            NumberValidator.validate_integer(value, min_value=0, max_value=2**63 - 1)
