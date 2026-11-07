from domain.exceptions import ValidationError


class PaymentProviderError(RuntimeError):
    pass


class InvalidPaymentAmountError(ValidationError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid payment amount: {reason}.")


class InvalidCurrencyError(ValidationError):
    def __init__(self) -> None:
        super().__init__("Currency must be a three-letter uppercase ASCII code.")


class InvalidPaymentStateError(ValidationError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid payment state: {reason}.")


class PaymentNotFoundError(InvalidPaymentStateError):
    def __init__(self) -> None:
        super().__init__("payment not found")


class InvalidPaymentSignatureError(InvalidPaymentStateError):
    def __init__(self) -> None:
        super().__init__("invalid postback signature")


class ImmutableTransactionError(ValidationError):
    def __init__(self) -> None:
        super().__init__(
            "Posted transactions cannot be changed or deleted; create a reversal instead."
        )
