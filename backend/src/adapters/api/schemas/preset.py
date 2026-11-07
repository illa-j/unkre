from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from adapters.api.schemas.common import (
    LoraStrengths,
    OptionalPrompt,
    PresetDescription,
    PresetName,
    PromptTuning,
    RequestModel,
    ResponseModel,
    Seed,
)
from domain.enums import PresetType

PreviewUrl = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=2048)
]
PreviewUrls = Annotated[list[PreviewUrl], Field(max_length=20)]


class CreatePresetRequest(PromptTuning):
    name: PresetName
    workflow_id: UUID
    prompt: OptionalPrompt = ""
    description: PresetDescription = ""
    is_public: bool = False
    preview_urls: PreviewUrls = Field(default_factory=list)


class PresetResponse(ResponseModel):
    id: UUID
    user_id: UUID | None
    type: PresetType
    name: str
    workflow_id: UUID
    prompt: str
    negative_prompt: str = ""
    description: str = ""
    loras_strength: dict[UUID, int | float]
    seed: int | None
    is_public: bool = False
    preview_urls: list[str] = Field(default_factory=list)
    favorites_count: int = 0
    is_favorite: bool = False
    likes_count: int = 0
    is_liked: bool = False
    is_saved: bool = False
    created_at: datetime | None
    updated_at: datetime | None


class UpdatePresetRequest(RequestModel):
    """Partial update: only the fields present in the payload are changed.

    An explicit ``null`` clears LoRA strengths or the fixed seed; omitting the
    field keeps the stored value.
    """

    name: PresetName | None = None
    workflow_id: UUID | None = None
    prompt: OptionalPrompt | None = None
    negative_prompt: OptionalPrompt | None = None
    description: PresetDescription | None = None
    loras_strength: LoraStrengths | None = None
    seed: Seed | None = None
    is_public: bool | None = None
    preview_urls: PreviewUrls | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> UpdatePresetRequest:
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        return self


class PresetPreviewResponse(ResponseModel):
    id: UUID
    url: str


class PresetFavoriteResponse(ResponseModel):
    favorites_count: int
    is_favorite: bool


class PresetLikeResponse(ResponseModel):
    likes_count: int
    is_liked: bool


class PresetSaveResponse(ResponseModel):
    is_saved: bool
