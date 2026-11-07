from datetime import datetime
from uuid import UUID

from adapters.api.schemas.common import (
    CreditAmount,
    OptionalCreditAmount,
    PromoCodeInput,
    RequestModel,
    ResponseModel,
)


class RedeemPromoCodeRequest(RequestModel):
    code: PromoCodeInput


class PromoRedemptionResponse(ResponseModel):
    code: str
    credits: int
    balance: int


class AdminPromoCodeCreateRequest(RequestModel):
    code: PromoCodeInput
    credits: CreditAmount
    max_redemptions: OptionalCreditAmount = None
    expires_at: datetime | None = None
    is_active: bool = True


class AdminPromoCodeUpdateRequest(RequestModel):
    is_active: bool


class AdminPromoCodeResponse(ResponseModel):
    id: UUID
    code: str
    credits: int
    max_redemptions: int | None
    redeemed_count: int
    expires_at: datetime | None
    is_active: bool
    created_at: datetime | None
