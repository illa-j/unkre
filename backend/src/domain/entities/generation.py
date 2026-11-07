from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.enums import GenerationStatus


@dataclass(kw_only=True)
class Generation:
    user_id: UUID
    workflow_id: UUID
    prompt: str
    negative_prompt: str = ""
    id: UUID | None = None
    loras_strength: dict[UUID, int | float] = field(default_factory=dict)
    uploaded_images: int = 0
    status: GenerationStatus = GenerationStatus.PENDING
    runpod_job_id: str | None = None
    runpod_endpoint_id: str | None = None
    seed: int | None = None
    error: str | None = None
    credits_spent: int | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
