from datetime import date, datetime
from uuid import UUID

from pydantic import model_validator

from adapters.api.schemas.common import (
    AdjustmentAmount,
    AdjustmentDescription,
    Collection,
    Page,
    RequestModel,
    ResponseModel,
    StrongPassword,
    Username,
)


class OverviewPoint(ResponseModel):
    date: date
    users: int
    generations: int
    credits_spent: int


class AdminOverviewResponse(ResponseModel):
    users_total: int
    users_blocked: int
    users_new_24h: int
    users_new_7d: int
    users_new_30d: int
    generations_total: int
    generations_24h: int
    generations_7d: int
    generations_active: int
    generations_by_status: dict[str, int]
    credits_spent_24h: int
    credits_spent_7d: int
    revenue_total: str
    revenue_30d: str
    credits_sold_30d: int
    payments_pending: int
    promo_redemptions: int
    daily: list[OverviewPoint]


class AdminUserItem(ResponseModel):
    id: UUID
    first_name: str
    last_name: str | None
    username: str | None
    google_email: str | None
    telegram_id: int | None
    photo_url: str | None
    credits: int
    is_blocked: bool
    registered_at: datetime
    last_active_at: datetime | None
    generations: int
    credits_spent: int


class UpdateUserRequest(RequestModel):
    is_blocked: bool


class UpdateUserResponse(ResponseModel):
    user_id: UUID
    is_blocked: bool


class AdjustCreditsRequest(RequestModel):
    amount: AdjustmentAmount
    description: AdjustmentDescription = "Manual adjustment"

    @model_validator(mode="after")
    def non_zero(self) -> AdjustCreditsRequest:
        if self.amount == 0:
            raise ValueError("amount must not be zero")
        return self


class AdjustCreditsResponse(ResponseModel):
    user_id: UUID
    credits: int


class AdminGenerationItem(ResponseModel):
    id: UUID
    user_id: UUID
    user_name: str
    user_email: str | None
    workflow: str
    prompt: str
    status: str
    credits_spent: int | None
    seed: int | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None


class AdminPaymentItem(ResponseModel):
    id: UUID
    user_id: UUID
    user_name: str
    provider: str
    status: str
    credits: int
    amount: str
    paid_amount: str | None
    currency: str
    created_at: datetime
    paid_at: datetime | None


class AdminRedemptionItem(ResponseModel):
    id: UUID
    user_id: UUID
    user_name: str
    user_email: str | None
    credits: int
    created_at: datetime


class AdminAccountItem(ResponseModel):
    id: UUID
    username: str
    is_owner: bool
    created_at: datetime


class CreateAdminRequest(RequestModel):
    username: Username
    password: StrongPassword
    is_owner: bool = False


AdminUserPage = Page[AdminUserItem]
AdminGenerationPage = Page[AdminGenerationItem]
AdminPaymentPage = Page[AdminPaymentItem]
AdminRedemptionPage = Page[AdminRedemptionItem]
AdminAccountPage = Collection[AdminAccountItem]
