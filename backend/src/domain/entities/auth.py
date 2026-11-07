from dataclasses import dataclass, field
from enum import StrEnum

from domain.entities.admin import Admin
from domain.entities.user import User
from domain.exceptions.auth import InvalidCredentialsError
from domain.validators import NumberValidator, TextValidator


class AuthProvider(StrEnum):
    GOOGLE = "google"
    TELEGRAM = "telegram"


@dataclass(frozen=True, kw_only=True)
class SocialIdentity:
    provider: AuthProvider
    subject: str
    first_name: str = "User"
    last_name: str | None = None
    email: str | None = None
    telegram_id: int | None = None
    username: str | None = None
    photo_url: str | None = None
    language_code: str | None = None
    # Telegram MiniApp exposes these alongside the profile fields.
    is_premium: bool | None = None
    allows_write_to_pm: bool | None = None
    added_to_attachment_menu: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", AuthProvider(self.provider))
        # sub є непрозорим ідентифікатором: пробіли та регістр не змінюємо.
        TextValidator.validate(self.subject, max_length=255)
        for name, limit, nullable in (
            ("first_name", 255, False),
            ("last_name", 255, True),
            ("username", 255, True),
            ("email", 320, self.provider != AuthProvider.GOOGLE),
            ("photo_url", 512, True),
            ("language_code", 10, True),
        ):
            value = TextValidator.validate(
                getattr(self, name), max_length=limit, strip=True, nullable=nullable
            )
            object.__setattr__(self, name, value)
        NumberValidator.validate_integer(
            self.telegram_id,
            min_value=1,
            max_value=2**63 - 1,
            nullable=self.provider != AuthProvider.TELEGRAM,
        )
        for name in ("is_premium", "allows_write_to_pm", "added_to_attachment_menu"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise InvalidCredentialsError(f"Invalid {name}")


@dataclass(frozen=True, kw_only=True)
class AuthChallenge:
    nonce: str = field(repr=False)
    client_id: str
    expires_in: int


@dataclass(frozen=True, kw_only=True)
class UserSession:
    user: User
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_in: int
    is_new_user: bool = False
    token_type: str = "bearer"


@dataclass(frozen=True, kw_only=True)
class AdminSession:
    admin: Admin
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_in: int
