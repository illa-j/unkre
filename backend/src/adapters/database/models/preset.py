from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, validates

from adapters.database.models import Base, TimestampMixin
from adapters.database.types import LoraStrengths, String8192, UUIDPrimaryKey
from domain.entities.preset import GenerationPreset
from domain.enums import PresetType
from domain.exceptions import InvalidPreviewUrlsError
from domain.validators import NumberValidator, TextValidator

preset_saves = Table(
    "preset_saves",
    Base.metadata,
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "preset_id",
        ForeignKey("generation_presets.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)

preset_favorites = Table(
    "preset_favorites",
    Base.metadata,
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "preset_id",
        ForeignKey("generation_presets.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)


class GenerationPresetModel(TimestampMixin, Base):
    __tablename__ = "generation_presets"

    id: Mapped[UUIDPrimaryKey]
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    type: Mapped[str] = mapped_column(
        String(10),
        default=PresetType.USER.value,
        server_default=PresetType.USER.value,
        nullable=False,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False, index=True
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt: Mapped[String8192] = mapped_column(default="", nullable=False)
    negative_prompt: Mapped[String8192] = mapped_column(
        default="", server_default="", nullable=False
    )
    description: Mapped[str] = mapped_column(
        String(1000), default="", server_default="", nullable=False
    )
    loras_strength: Mapped[LoraStrengths] = mapped_column(
        MutableDict.as_mutable(JSONB().with_variant(JSON(), "sqlite")),
        default=dict,
        nullable=False,
    )
    seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    preview_urls: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB().with_variant(JSON(), "sqlite")),
        default=list,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 100 AND length(name) <= 100",
            name="check_generation_presets_name_length",
        ),
        CheckConstraint(
            "length(prompt) <= 8192",
            name="check_generation_presets_prompt_length",
        ),
        CheckConstraint(
            "length(negative_prompt) <= 8192",
            name="check_generation_presets_negative_prompt_length",
        ),
        CheckConstraint(
            "length(description) <= 1000",
            name="check_generation_presets_description_length",
        ),
        CheckConstraint(
            "seed IS NULL OR seed BETWEEN 0 AND 9223372036854775807",
            name="check_generation_presets_seed_range",
        ),
        CheckConstraint(
            "type IN ('user', 'admin')",
            name="check_generation_presets_type",
        ),
        CheckConstraint(
            "(type = 'user' AND user_id IS NOT NULL) "
            "OR (type = 'admin' AND user_id IS NULL)",
            name="check_generation_presets_owner_type",
        ),
        CheckConstraint(
            "json_type(preview_urls) = 'array'",
            name="check_generation_presets_preview_urls_array",
        ).ddl_if(dialect="sqlite"),
        CheckConstraint(
            "jsonb_typeof(preview_urls) = 'array'",
            name="check_generation_presets_preview_urls_array",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "json_type(loras_strength) = 'object'",
            name="check_generation_presets_loras_strength_object",
        ).ddl_if(dialect="sqlite"),
        CheckConstraint(
            "jsonb_typeof(loras_strength) = 'object'",
            name="check_generation_presets_loras_strength_object",
        ).ddl_if(dialect="postgresql"),
    )

    @validates("name")
    def validate_name(self, key: str, value: str) -> str:
        return TextValidator.validate(value, max_length=100, strip=True)

    @validates("prompt")
    def validate_prompt(self, key: str, value: str) -> str:
        return TextValidator.validate(value, min_length=0, max_length=8192)

    @validates("negative_prompt")
    def validate_negative_prompt(self, key: str, value: str) -> str:
        return TextValidator.validate(value, min_length=0, max_length=8192)

    @validates("description")
    def validate_description(self, key: str, value: str) -> str:
        return TextValidator.validate(value, min_length=0, max_length=1000)

    @validates("preview_urls")
    def validate_preview_urls(self, key: str, value: list[str]) -> list[str]:
        if not isinstance(value, list) or any(
            not isinstance(url, str) or not url.strip() for url in value
        ):
            raise InvalidPreviewUrlsError()
        return list(value)

    @validates("seed")
    def validate_seed(self, key: str, value: int | None) -> int | None:
        return NumberValidator.validate_integer(
            value, min_value=0, max_value=2**63 - 1, nullable=True
        )

    def to_entity(
        self,
        *,
        favorites_count: int = 0,
        is_favorite: bool = False,
        is_saved: bool = False,
    ) -> GenerationPreset:
        return GenerationPreset(
            id=self.id,
            user_id=self.user_id,
            workflow_id=self.workflow_id,
            name=self.name,
            prompt=self.prompt,
            negative_prompt=self.negative_prompt,
            description=self.description,
            loras_strength={
                uuid.UUID(ident): strength
                for ident, strength in self.loras_strength.items()
            },
            type=PresetType(self.type),
            is_public=bool(self.is_public),
            preview_urls=list(self.preview_urls or []),
            seed=self.seed,
            favorites_count=favorites_count,
            is_favorite=is_favorite,
            likes_count=favorites_count,
            is_liked=is_favorite,
            is_saved=is_saved,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, preset: GenerationPreset) -> GenerationPresetModel:
        return cls(
            id=preset.id,
            user_id=preset.user_id,
            workflow_id=preset.workflow_id,
            name=preset.name,
            prompt=preset.prompt,
            negative_prompt=preset.negative_prompt,
            description=preset.description,
            loras_strength={
                str(ident): strength
                for ident, strength in preset.loras_strength.items()
            },
            type=preset.type.value,
            is_public=preset.is_public,
            preview_urls=list(preset.preview_urls),
            seed=preset.seed,
        )
