from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from adapters.database.models import Base, TimestampMixin
from adapters.database.types import String255, Timestamp, UUIDPrimaryKey
from adapters.security import PasswordSecurity
from domain.entities import Admin, AdminRefreshToken
from domain.security import TokenManager
from domain.validators import AuthValidator, TextValidator


class AdminModel(TimestampMixin, Base):
    __tablename__ = "admins"

    id: Mapped[UUIDPrimaryKey]
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    _hashed_password: Mapped[String255] = mapped_column("hashed_password")
    is_owner: Mapped[bool] = mapped_column(default=False, nullable=False)

    refresh_tokens: Mapped[list[AdminRefreshTokenModel]] = relationship(
        "AdminRefreshTokenModel", back_populates="admin", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AdminModel(id={self.id}, username={self.username})>"

    @classmethod
    def create(
        cls, username: str, raw_password: str, is_owner: bool = False
    ) -> AdminModel:
        admin = cls(username=username, is_owner=is_owner)
        admin.password = raw_password
        return admin

    __table_args__ = (
        CheckConstraint(
            "length(trim(username)) BETWEEN 2 AND 100 AND length(username) <= 100",
            name="check_admin_username_length",
        ),
        CheckConstraint(
            "length(hashed_password) BETWEEN 1 AND 255",
            name="check_admin_hashed_password_length",
        ),
    )

    @validates("username")
    def validate_username(self, key: str, value: str) -> str:
        return TextValidator.validate(value, min_length=2, max_length=100, strip=True)

    @property
    def password(self) -> None:
        raise AttributeError(
            "Password is write-only. Use the setter to set the password."
        )

    @password.setter
    def password(self, raw_password: str) -> None:
        AuthValidator.validate_password_strength(raw_password)
        self._hashed_password = PasswordSecurity.hash_password(raw_password)

    def verify_password(self, raw_password: str) -> bool:
        return PasswordSecurity.verify_password(raw_password, self._hashed_password)

    def to_entity(self) -> Admin:
        return Admin(
            id=self.id,
            username=self.username,
            is_owner=self.is_owner,
            hashed_password=self._hashed_password,
        )

    @classmethod
    def from_entity(cls, admin: Admin) -> AdminModel:
        model = cls(username=admin.username, is_owner=admin.is_owner)
        if admin.password:
            model.password = admin.password
        elif admin.hashed_password:
            model._hashed_password = admin.hashed_password
        if admin.id is not None:
            model.id = admin.id
        return model

    def needs_rehash(self) -> bool:
        return PasswordSecurity.needs_rehash(self._hashed_password)

    def verify_and_maybe_rehash(self, raw_password: str) -> bool:
        is_valid = PasswordSecurity.verify_password(raw_password, self._hashed_password)
        if is_valid and PasswordSecurity.needs_rehash(self._hashed_password):
            self._hashed_password = PasswordSecurity.hash_password(raw_password)
        return is_valid


class AdminTokenBaseModel(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
    _hashed_token: Mapped[str] = mapped_column(String(100), unique=True)
    expires_at: Mapped[Timestamp] = mapped_column(
        default=lambda: datetime.now(UTC) + timedelta(days=1),
    )
    admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("admins.id", ondelete="CASCADE"), index=True
    )

    __table_args__: tuple | None = (UniqueConstraint("admin_id"),)

    @property
    def token(self) -> str:
        raise AttributeError("Token is write-only. Use the setter to set the token.")

    @token.setter
    def token(self, value: str) -> None:
        self._hashed_token = TokenManager.hash_token(value)

    def verify_token(self, plain_token: str) -> bool:
        return TokenManager.verify_token(plain_token, self._hashed_token)


class AdminRefreshTokenModel(AdminTokenBaseModel):
    __tablename__ = "admin_refresh_tokens"
    __table_args__ = (
        CheckConstraint("id > 0", name="check_admin_refresh_tokens_id_positive"),
        CheckConstraint(
            "length(_hashed_token) BETWEEN 1 AND 100",
            name="check_admin_refresh_tokens_hashed_token_length",
        ),
    )

    admin: Mapped[AdminModel] = relationship(
        "AdminModel", back_populates="refresh_tokens"
    )

    @classmethod
    def create(
        cls, admin_id: uuid.UUID, days_valid: int, token: str
    ) -> AdminRefreshTokenModel:
        expires_at = datetime.now(UTC) + timedelta(days=days_valid)
        instance = cls(admin_id=admin_id, expires_at=expires_at)
        instance.token = token
        return instance

    def __repr__(self):
        return f"<AdminRefreshTokenModel(id={self.id}, expires_at={self.expires_at})>"

    def to_entity(self) -> AdminRefreshToken:
        return AdminRefreshToken(
            id=self.id,
            admin_id=self.admin_id,
            expires_at=self.expires_at,
        )
