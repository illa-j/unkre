from enum import StrEnum


class PaymentProvider(StrEnum):
    TELEGRAM_STARS = "telegram_stars"
    ATLOS = "atlos"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
