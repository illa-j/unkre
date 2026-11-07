from domain.exceptions import ValidationError


class PromoCodeError(ValidationError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Promo code error: {reason}.")


class InvalidPromoCodeError(PromoCodeError):
    pass


class PromoCodeNotFoundError(PromoCodeError):
    def __init__(self) -> None:
        super().__init__("unknown promo code")


class PromoCodeConflictError(PromoCodeError):
    pass


class PromoCodeAlreadyRedeemedError(PromoCodeConflictError):
    def __init__(self) -> None:
        super().__init__("this code has already been used on this account")


class PromoCodeInactiveError(PromoCodeConflictError):
    def __init__(self) -> None:
        super().__init__("this code is no longer active")


class PromoCodeExpiredError(PromoCodeConflictError):
    def __init__(self) -> None:
        super().__init__("this code has expired")


class PromoCodeExhaustedError(PromoCodeConflictError):
    def __init__(self) -> None:
        super().__init__("this code has reached its redemption limit")


class PromoCodeDuplicateError(PromoCodeConflictError):
    def __init__(self) -> None:
        super().__init__("a promo code with this name already exists")
