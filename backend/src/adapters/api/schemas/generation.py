from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from adapters.api.schemas.common import (
    MAX_REFERENCE_IMAGES,
    Prompt,
    PromptTuning,
    ReferenceImage,
    ResponseModel,
)
from domain.enums import GenerationStatus


class CreateGenerationRequest(PromptTuning):
    workflow_id: UUID
    prompt: Prompt
    images: Annotated[
        list[ReferenceImage], Field(max_length=MAX_REFERENCE_IMAGES)
    ] = Field(default_factory=list)


class GenerationResponse(ResponseModel):
    id: UUID
    workflow_id: UUID
    prompt: str
    negative_prompt: str = ""
    loras_strength: dict[UUID, int | float]
    uploaded_images: int
    status: GenerationStatus
    seed: int | None
    error: str | None
    credits_spent: int | None
    completed_at: datetime | None
    created_at: datetime | None
