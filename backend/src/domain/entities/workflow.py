from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Lora:
    id: UUID
    name: str
    description: str | None = None
    preview_urls: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class Workflow:
    id: UUID
    name: str
    description: str | None = None
    generation_credits: int = 1
    loras: tuple[Lora, ...] = field(default_factory=tuple)
