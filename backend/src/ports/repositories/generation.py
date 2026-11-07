from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from domain.entities.generation import Generation
from domain.entities.workflow import Workflow


class GenerationRepositoryInterface(Protocol):
    async def create_generation(self, generation: Generation) -> Generation: ...

    async def get_generation(self, generation_id: UUID) -> Generation | None: ...

    async def get_generations(self, *, limit: int, offset: int) -> list[Generation]: ...

    async def update_generation(
        self, generation_id: UUID, values: Mapping[str, object]
    ) -> Generation | None: ...

    async def delete_generation(self, generation_id: UUID) -> bool: ...

    async def get_for_user(
        self, user_id: UUID, generation_id: UUID
    ) -> Generation | None: ...

    async def list_for_user(
        self, user_id: UUID, *, limit: int, offset: int
    ) -> list[Generation]: ...

    async def delete_for_user(self, user_id: UUID, generation_id: UUID) -> bool: ...


class WorkflowRepositoryInterface(Protocol):
    async def get_workflow(self, workflow_id: UUID) -> Workflow | None: ...
