from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates

from adapters.database.models import Base, TimestampMixin
from domain.entities.system_setting import SystemSetting
from domain.validators import TextValidator


class SystemSettingModel(TimestampMixin, Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "length(trim(key)) BETWEEN 1 AND 100 AND length(key) <= 100",
            name="check_system_settings_key_length",
        ),
        CheckConstraint(
            "description IS NULL OR length(description) <= 500",
            name="check_system_settings_description_length",
        ),
    )

    @validates("key")
    def validate_key(self, key: str, value: str) -> str:
        return TextValidator.validate(value, max_length=100, strip=True)

    @validates("description")
    def validate_description(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(
            value, min_length=0, max_length=500, nullable=True
        )

    def to_entity(self) -> SystemSetting:
        return SystemSetting(
            key=self.key,
            value=self.value,
            description=self.description,
            updated_by=self.updated_by,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, setting: SystemSetting) -> SystemSettingModel:
        return cls(
            key=setting.key,
            value=setting.value,
            description=setting.description,
            updated_by=setting.updated_by,
        )
