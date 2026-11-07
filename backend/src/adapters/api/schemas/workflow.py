from uuid import UUID

from pydantic import Field

from adapters.api.schemas.common import GenerationCredits, RequestModel, ResponseModel


class UpdateWorkflowCreditsRequest(RequestModel):
    generation_credits: GenerationCredits


class LoraResponse(ResponseModel):
    id: UUID
    name: str
    description: str | None
    preview_urls: list[str]
    is_nsfw: bool = False


class WorkflowResponse(ResponseModel):
    id: UUID
    name: str
    description: str | None
    generation_credits: int
    loras: list[LoraResponse]
    is_active: bool = True
    # LoRA id -> strength recommended by its author for this workflow.
    recommended_strengths: dict[UUID, float] = Field(default_factory=dict)
