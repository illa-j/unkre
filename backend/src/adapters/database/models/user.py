from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from adapters.database.models import Base, TimestampMixin, WalletModel
from adapters.database.types import String255, Timestamp, UUIDPrimaryKey
from domain.entities import User, UserRefreshToken
from domain.security import TokenManager
from domain.validators import NumberValidator, TextValidator

if TYPE_CHECKING:
    from adapters.database.models import GenerationModel, PaymentModel


class UserModel(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[UUIDPrimaryKey]

    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True, index=True, nullable=True
    )
    google_sub: Mapped[String255 | None] = mapped_column(
        unique=True, index=True, nullable=True
    )
    google_email: Mapped[str | None] = mapped_column(
        String(320), index=True, nullable=True
    )
    username: Mapped[String255 | None] = mapped_column(nullable=True)
    first_name: Mapped[String255] = mapped_column(index=True)
    last_name: Mapped[String255 | None] = mapped_column(nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_premium: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    allows_write_to_pm: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    added_to_attachment_menu: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )

    referral_code: Mapped[str] = mapped_column(
        String(24),
        unique=True,
        default=lambda: secrets.token_hex(12),
        server_default=text(
            "substr(replace(CAST(gen_random_uuid() AS TEXT), '-', ''), 1, 24)"
        ),
    )

    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_active_at: Mapped[Timestamp | None] = mapped_column(nullable=True)

    wallet: Mapped[WalletModel | None] = relationship(
        "WalletModel",
        back_populates="user",
        uselist=False,
        lazy="selectin",
        passive_deletes="all",
    )

    generations: Mapped[list[GenerationModel]] = relationship(
        "GenerationModel", back_populates="user"
    )

    refresh_tokens: Mapped[list[UserRefreshTokenModel]] = relationship(
        "UserRefreshTokenModel", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "google_sub IS NULL OR (length(google_sub) BETWEEN 1 AND 255)",
            name="check_users_google_sub_length",
        ),
        CheckConstraint(
            "google_email IS NULL OR (length(trim(google_email)) BETWEEN 1 AND 320 AND length(google_email) <= 320)",
            name="check_users_google_email_length",
        ),
        CheckConstraint(
            "username IS NULL OR (length(trim(username)) BETWEEN 1 AND 255 AND length(username) <= 255)",
            name="check_users_username_length",
        ),
        CheckConstraint(
            "length(trim(first_name)) BETWEEN 1 AND 255 AND length(first_name) <= 255",
            name="check_users_first_name_length",
        ),
        CheckConstraint(
            "last_name IS NULL OR (length(trim(last_name)) BETWEEN 1 AND 255 AND length(last_name) <= 255)",
            name="check_users_last_name_length",
        ),
        CheckConstraint(
            "language_code IS NULL OR (length(trim(language_code)) BETWEEN 1 AND 10 AND length(language_code) <= 10)",
            name="check_users_language_code_length",
        ),
        CheckConstraint(
            "photo_url IS NULL OR (length(photo_url) BETWEEN 1 AND 512)",
            name="check_users_photo_url_length",
        ),
        CheckConstraint(
            "length(referral_code) = 24", name="check_users_referral_code_length"
        ),
        CheckConstraint(
            "telegram_id IS NULL OR telegram_id BETWEEN 1 AND 9223372036854775807",
            name="check_users_telegram_id_range",
        ),
    )

    @validates("telegram_id")
    def validate_telegram_id(self, key: str, value: int | None) -> int | None:
        return NumberValidator.validate_integer(
            value, min_value=1, max_value=2**63 - 1, nullable=True
        )

    @validates("first_name")
    def validate_first_name(self, key: str, value: str) -> str:
        return TextValidator.validate(value, max_length=255, strip=True)

    @validates("username", "last_name")
    def validate_optional_name(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(value, max_length=255, strip=True, nullable=True)

    @validates("google_sub")
    def validate_google_sub(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(value, max_length=255, nullable=True)

    @validates("google_email")
    def validate_google_email(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(value, max_length=320, strip=True, nullable=True)

    @validates("language_code")
    def validate_language_code(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(value, max_length=10, strip=True, nullable=True)

    @validates("photo_url")
    def validate_photo_url(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(value, max_length=512, nullable=True)

    @validates("referral_code")
    def validate_referral_code(self, key: str, value: str) -> str:
        return TextValidator.validate(value, min_length=24, max_length=24)

    @property
    def credits(self) -> int:
        return (self.wallet.credits or 0) if self.wallet is not None else 0

    @property
    def payments(self) -> list[PaymentModel]:
        return self.wallet.payments if self.wallet is not None else []

    def to_entity(self) -> User:
        return User(
            id=self.id,
            telegram_id=self.telegram_id,
            username=self.username,
            first_name=self.first_name,
            last_name=self.last_name,
            language_code=self.language_code,
            photo_url=self.photo_url,
            is_premium=self.is_premium,
            allows_write_to_pm=self.allows_write_to_pm,
            added_to_attachment_menu=self.added_to_attachment_menu,
            credits=self.credits,
            referral_code=self.referral_code,
            is_blocked=self.is_blocked,
            registered_at=self.created_at,
            last_active_at=self.last_active_at,
            google_sub=self.google_sub,
            google_email=self.google_email,
        )

    @classmethod
    def from_entity(cls, user: User) -> UserModel:
        return cls(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
            photo_url=user.photo_url,
            is_premium=user.is_premium,
            allows_write_to_pm=user.allows_write_to_pm,
            added_to_attachment_menu=user.added_to_attachment_menu,
            wallet=WalletModel(credits=user.credits),
            **({"referral_code": user.referral_code} if user.referral_code else {}),
            is_blocked=user.is_blocked,
            last_active_at=user.last_active_at,
            google_sub=user.google_sub,
            google_email=user.google_email,
        )


class UserTokenBaseModel(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
    _hashed_token: Mapped[str] = mapped_column(String(100), unique=True)
    expires_at: Mapped[Timestamp] = mapped_column(
        default=lambda: datetime.now(UTC) + timedelta(days=1),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    __table_args__: tuple | None = (UniqueConstraint("user_id"),)

    @property
    def token(self) -> str:
        raise AttributeError("Token is write-only. Use the setter to set the token.")

    @token.setter
    def token(self, value: str) -> None:
        self._hashed_token = TokenManager.hash_token(value)

    def verify_token(self, plain_token: str) -> bool:
        return TokenManager.verify_token(plain_token, self._hashed_token)


class UserRefreshTokenModel(UserTokenBaseModel):
    __tablename__ = "user_refresh_tokens"
    __table_args__ = (
        CheckConstraint("id > 0", name="check_user_refresh_tokens_id_positive"),
        CheckConstraint(
            "length(_hashed_token) BETWEEN 1 AND 100",
            name="check_user_refresh_tokens_hashed_token_length",
        ),
    )

    user: Mapped[UserModel] = relationship("UserModel", back_populates="refresh_tokens")

    @classmethod
    def create(
        cls, user_id: uuid.UUID, days_valid: int, token: str
    ) -> UserRefreshTokenModel:
        expires_at = datetime.now(UTC) + timedelta(days=days_valid)
        instance = cls(user_id=user_id, expires_at=expires_at)
        instance.token = token
        return instance

    def __repr__(self):
        return f"<UserRefreshTokenModel(id={self.id}, expires_at={self.expires_at})>"

    def to_entity(self) -> UserRefreshToken:
        return UserRefreshToken(
            id=self.id,
            user_id=self.user_id,
            expires_at=self.expires_at,
        )
