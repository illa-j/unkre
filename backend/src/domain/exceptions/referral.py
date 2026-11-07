from domain.exceptions import ValidationError


class InvalidReferralError(ValidationError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid referral: {reason}.")


class ReferralNotFoundError(InvalidReferralError):
    def __init__(self) -> None:
        super().__init__("referral code not found")
