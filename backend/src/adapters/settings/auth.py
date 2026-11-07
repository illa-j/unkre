from pydantic import Field

from adapters.settings.base import BaseAppSettings


class AuthSettings(BaseAppSettings):
    GOOGLE_CLIENT_ID: str = ""
    TELEGRAM_CLIENT_ID: str = ""
    AUTH_CHALLENGE_TTL_SECONDS: int = Field(default=300, ge=30, le=900)
    USER_INITIAL_CREDITS: int = Field(default=15, ge=0)
    REFERRAL_INVITER_CREDITS: int = Field(default=50, ge=0, le=2**31 - 1)
    REFERRAL_INVITEE_CREDITS: int = Field(default=50, ge=0, le=2**31 - 1)
