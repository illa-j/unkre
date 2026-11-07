from datetime import datetime
from uuid import UUID

from adapters.api.schemas.common import (
    Nonce,
    ReferralCode,
    RequestModel,
    ResponseModel,
    Token,
)
from domain.entities.auth import AuthProvider


class AuthChallengeRequest(RequestModel):
    provider: AuthProvider


class ProviderTokenRequest(RequestModel):
    """OIDC credentials issued by Google or Telegram Login."""

    id_token: Token
    nonce: Nonce


class SocialLoginRequest(ProviderTokenRequest):
    referral_code: ReferralCode | None = None


class AccountLinkRequest(ProviderTokenRequest):
    pass


class TelegramWebAppLoginRequest(RequestModel):
    init_data: Token
    referral_code: ReferralCode | None = None


class UserResponse(ResponseModel):
    id: UUID
    first_name: str
    last_name: str | None
    username: str | None
    telegram_id: int | None
    google_email: str | None
    language_code: str | None
    photo_url: str | None
    is_premium: bool | None
    allows_write_to_pm: bool | None
    added_to_attachment_menu: bool | None
    credits: int
    referral_code: str
    registered_at: datetime
    last_active_at: datetime | None


class UserSessionResponse(ResponseModel):
    user: UserResponse
    expires_in: int
    is_new_user: bool
