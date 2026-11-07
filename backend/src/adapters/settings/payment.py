from decimal import Decimal

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from adapters.settings.base import BaseAppSettings


class PaymentSettings(BaseAppSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True)

    CRYPTO_PRICE_PER_CREDIT: Decimal | None = Field(
        default=Decimal("0.01"), gt=0, max_digits=38, decimal_places=18
    )
    CRYPTO_CURRENCY: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    STARS_PRICE_PER_CREDIT: int | None = Field(default=5, ge=1, le=2**31 - 1)
    CRYPTO_MIN_AMOUNT: Decimal = Field(
        default=Decimal("1"), gt=0, max_digits=38, decimal_places=18
    )
    STARS_MIN_AMOUNT: int = Field(default=100, ge=1, le=2**31 - 1)
    ATLOS_MERCHANT_ID: str = ""
    ATLOS_API_SECRET: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = Field(default="", pattern=r"^[A-Za-z0-9_-]{0,256}$")
    PAYMENT_INVOICE_TTL_SECONDS: int = Field(default=3600, ge=1)
    PAYMENT_PROVIDER_TIMEOUT_SECONDS: float = Field(default=10, ge=0.1)
    # Public endpoint that ATLOS should POST to. Per-invoice PostbackUrl is
    # sent with Invoice/Create so the merchant panel setting is not required.
    PAYMENT_POSTBACK_URL: str = ""
