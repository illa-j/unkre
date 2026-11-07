from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.enums import PresetType


@dataclass(kw_only=True)
class GenerationPreset:
    user_id: UUID | None
    workflow_id: UUID
    name: str
    prompt: str
    negative_prompt: str = ""
    description: str = ""
    id: UUID | None = None
    type: PresetType = PresetType.USER
    is_public: bool = False
    preview_urls: list[str] = field(default_factory=list)
    loras_strength: dict[UUID, int | float] = field(default_factory=dict)
    seed: int | None = None
    favorites_count: int = 0
    is_favorite: bool = False
    likes_count: int = 0
    is_liked: bool = False
    is_saved: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
