from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, CheckConstraint, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from adapters.database.models import Base, TimestampMixin, workflow_loras
from adapters.database.types import String255, String4096, UUIDPrimaryKey
from domain.exceptions import InvalidPreviewUrlsError
from domain.validators import TextValidator

if TYPE_CHECKING:
    from adapters.database.models import WorkflowModel


class LoraModel(TimestampMixin, Base):
    __tablename__ = "loras"

    id: Mapped[UUIDPrimaryKey]
    name: Mapped[String255] = mapped_column(index=True)
    description: Mapped[String4096 | None] = mapped_column(nullable=True)
    preview_urls: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB().with_variant(JSON(), "sqlite")),
        default=list,
        nullable=False,
    )
    is_nsfw: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    workflows: Mapped[list[WorkflowModel]] = relationship(
        "WorkflowModel", secondary=workflow_loras, back_populates="loras"
    )

    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 255 AND length(name) <= 255",
            name="check_loras_name_length",
        ),
        CheckConstraint(
            "description IS NULL OR length(description) <= 4096",
            name="check_loras_description_length",
        ),
        CheckConstraint(
            "jsonb_typeof(preview_urls) = 'array'",
            name="check_loras_preview_urls_array",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "json_type(preview_urls) = 'array'", name="check_loras_preview_urls_array"
        ).ddl_if(dialect="sqlite"),
    )

    @validates("name")
    def validate_name(self, key: str, value: str) -> str:
        return TextValidator.validate(value, max_length=255, strip=True)

    @validates("description")
    def validate_description(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(
            value, min_length=0, max_length=4096, nullable=True
        )

    @validates("preview_urls")
    def validate_preview_urls(self, key: str, value: list[str]) -> list[str]:
        if not isinstance(value, list) or any(
            not isinstance(url, str) or not url.strip() for url in value
        ):
            raise InvalidPreviewUrlsError()
        return list(value)
