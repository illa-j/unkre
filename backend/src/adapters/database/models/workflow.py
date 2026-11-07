from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Table,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from adapters.database.models import Base, TimestampMixin
from adapters.database.types import String255, String4096, UUIDPrimaryKey
from domain.validators import NumberValidator, TextValidator

if TYPE_CHECKING:
    from adapters.database.models import GenerationModel, LoraModel


workflow_loras = Table(
    "workflow_loras",
    Base.metadata,
    Column(
        "workflow_id",
        UUID,
        ForeignKey("workflows.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "lora_id", UUID, ForeignKey("loras.id", ondelete="CASCADE"), primary_key=True
    ),
    # Strength recommended by the LoRA author for this exact workflow.
    Column("recommended_strength", Float, nullable=True),
)


class WorkflowModel(TimestampMixin, Base):
    __tablename__ = "workflows"

    id: Mapped[UUIDPrimaryKey]
    name: Mapped[String255] = mapped_column(index=True)
    description: Mapped[String4096 | None] = mapped_column(nullable=True)
    generation_credits: Mapped[int] = mapped_column(
        default=1, server_default="1", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )

    loras: Mapped[list[LoraModel]] = relationship(
        "LoraModel",
        secondary=workflow_loras,
        back_populates="workflows",
        lazy="selectin",
    )
    generations: Mapped[list[GenerationModel]] = relationship(
        "GenerationModel", back_populates="workflow", passive_deletes="all"
    )

    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 255 AND length(name) <= 255",
            name="check_workflows_name_length",
        ),
        CheckConstraint(
            "description IS NULL OR length(description) <= 4096",
            name="check_workflows_description_length",
        ),
        CheckConstraint(
            "generation_credits BETWEEN 0 AND 2147483647",
            name="check_workflows_generation_credits_range",
        ),
    )

    @validates("name")
    def validate_name(self, key: str, value: str) -> str:
        return TextValidator.validate(value, max_length=255, strip=True)

    @validates("generation_credits")
    def validate_generation_credits(self, key: str, value: int) -> int:
        return NumberValidator.validate_integer(
            value, min_value=0, max_value=2**31 - 1
        )

    @validates("description")
    def validate_description(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(
            value, min_length=0, max_length=4096, nullable=True
        )
