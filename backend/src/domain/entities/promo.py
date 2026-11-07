import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid7

from domain.exceptions.promo import InvalidPromoCodeError
from domain.validators import NumberValidator

PROMO_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,63}$")


def normalize_promo_code(value: object) -> str:
    if not isinstance(value, str):
        raise InvalidPromoCodeError("a promo code must be text")
    code = value.strip().upper()
    if not PROMO_CODE_PATTERN.fullmatch(code):
        raise InvalidPromoCodeError(
            "use 3–64 letters, numbers, dashes or underscores"
        )
    return code


@dataclass(frozen=True, kw_only=True)
class PromoCode:
    code: str
    credits: int
    max_redemptions: int | None = None
    redeemed_count: int = 0
    expires_at: datetime | None = None
    is_active: bool = True
    id: UUID = field(default_factory=uuid7)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalize_promo_code(self.code))
        NumberValidator.validate_integer(self.credits, min_value=1, max_value=2**31 - 1)
        NumberValidator.validate_integer(
            self.max_redemptions, min_value=1, max_value=2**31 - 1, nullable=True
        )
        NumberValidator.validate_integer(
            self.redeemed_count, min_value=0, max_value=2**31 - 1
        )
        if (
            self.max_redemptions is not None
            and self.redeemed_count > self.max_redemptions
        ):
            raise InvalidPromoCodeError("redemptions exceed the code limit")
        if self.expires_at is not None:
            if not isinstance(self.expires_at, datetime) or self.expires_at.tzinfo is None:
                raise InvalidPromoCodeError("the expiry must be timezone-aware")
            object.__setattr__(self, "expires_at", self.expires_at.astimezone(UTC))
        if not isinstance(self.is_active, bool):
            raise InvalidPromoCodeError("is_active must be a boolean")

    def is_expired(self, now: datetime | None = None) -> bool:
        return self.expires_at is not None and self.expires_at <= (now or datetime.now(UTC))

    def is_exhausted(self) -> bool:
        return (
            self.max_redemptions is not None
            and self.redeemed_count >= self.max_redemptions
        )


@dataclass(frozen=True, kw_only=True)
class PromoRedemption:
    promo_code_id: UUID
    user_id: UUID
    credits: int
    id: UUID = field(default_factory=uuid7)
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        NumberValidator.validate_integer(self.credits, min_value=1, max_value=2**31 - 1)
