from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from adapters.api.schemas.common import (
    GenerationCredits,
    Page,
    RequestModel,
    ResponseModel,
)

WorkflowName = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=255),
]
CatalogDescription = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, max_length=4096),
]
LoraFileName = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=255),
]
PreviewUrl = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=2048)
]


class CreateWorkflowRequest(RequestModel):
    name: WorkflowName
    description: CatalogDescription | None = None
    generation_credits: GenerationCredits = 1
    is_active: bool = True


class UpdateWorkflowRequest(RequestModel):
    description: CatalogDescription | None = None
    generation_credits: GenerationCredits | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> UpdateWorkflowRequest:
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        return self


class WorkflowLoraItem(RequestModel):
    lora_id: UUID
    recommended_strength: Annotated[float, Field(ge=0, le=2)] | None = None


class SetWorkflowLorasRequest(RequestModel):
    items: list[WorkflowLoraItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_loras(self) -> SetWorkflowLorasRequest:
        ids = [item.lora_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate LoRA in the list")
        return self


class CreateLoraRequest(RequestModel):
    name: LoraFileName
    description: CatalogDescription | None = None
    preview_urls: Annotated[list[PreviewUrl], Field(max_length=20)] = Field(
        default_factory=list
    )
    is_nsfw: bool = False


class UpdateLoraRequest(RequestModel):
    description: CatalogDescription | None = None
    preview_urls: Annotated[list[PreviewUrl], Field(max_length=20)] | None = None
    is_nsfw: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> UpdateLoraRequest:
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        return self


class AdminLoraItem(ResponseModel):
    id: UUID
    name: str
    description: str | None
    preview_urls: list[str]
    is_nsfw: bool = False
    workflow_count: int = 0


AdminLoraPage = Page[AdminLoraItem]
