from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import Field

from adapters.api.schemas.common import (
    CreditAmount,
    IdempotencyKey,
    RequestModel,
    ResponseModel,
)
from domain.enums import PaymentProvider, PaymentStatus


class CreatePaymentRequest(RequestModel):
    credits: CreditAmount
    idempotency_key: IdempotencyKey


class PaymentResponse(ResponseModel):
    id: UUID
    provider: PaymentProvider
    status: PaymentStatus
    credits: int
    amount: Decimal
    currency: str
    paid_amount: Decimal | None
    checkout_url: str | None
    expires_at: datetime | None
    paid_at: datetime | None
    created_at: datetime | None


class PaymentPricesResponse(ResponseModel):
    crypto_price_per_credit: Decimal | None
    crypto_currency: str
    stars_price_per_credit: int | None
    crypto_min_amount: Decimal
    stars_min_amount: int


class TelegramPaymentUpdateRequest(RequestModel):
    update_id: Annotated[int, Field(strict=True, ge=0)]
    pre_checkout_query: dict[str, Any] | None = None
    message: dict[str, Any] | None = None
