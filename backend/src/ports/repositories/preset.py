from typing import Protocol
from uuid import UUID

from domain.entities.preset import GenerationPreset


class PresetRepositoryInterface(Protocol):
    async def create_preset(self, preset: GenerationPreset) -> GenerationPreset: ...

    async def get_for_user(
        self, user_id: UUID, preset_id: UUID
    ) -> GenerationPreset | None: ...

    async def get_accessible(
        self, user_id: UUID, preset_id: UUID
    ) -> GenerationPreset | None: ...

    async def list_for_user(
        self, user_id: UUID, *, limit: int, offset: int
    ) -> list[GenerationPreset]: ...

    async def update_for_user(
        self, user_id: UUID, preset_id: UUID, values: dict[str, object]
    ) -> GenerationPreset | None: ...

    async def delete_for_user(self, user_id: UUID, preset_id: UUID) -> bool: ...

    async def get_any(self, preset_id: UUID) -> GenerationPreset | None: ...

    async def update_any(
        self, preset_id: UUID, values: dict[str, object]
    ) -> GenerationPreset | None: ...

    async def delete_any(self, preset_id: UUID) -> bool: ...

    async def list_any(
        self, *, query: str | None, limit: int, offset: int
    ) -> tuple[list[GenerationPreset], int]: ...

    async def favorite(self, user_id: UUID, preset_id: UUID) -> int: ...

    async def unfavorite(self, user_id: UUID, preset_id: UUID) -> int: ...
