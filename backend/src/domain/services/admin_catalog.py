from collections.abc import Sequence
from uuid import UUID

from adapters.api.schemas.admin_catalog import AdminLoraItem
from adapters.api.schemas.workflow import WorkflowResponse
from adapters.api.workflow_view import workflow_responses
from adapters.database.models import LoraModel, WorkflowModel
from adapters.database.repositiries.admin_catalog import AdminCatalogRepository
from domain.exceptions.catalog import (
    LoraInUseError,
    LoraNameConflictError,
    WorkflowHasHistoryError,
    WorkflowNameConflictError,
)
from domain.validators import (
    NumberValidator,
    TextValidator,
    validate_lora_strength,
    validate_preview_urls,
)

CATALOG_NAME_MAX = 255
DESCRIPTION_MAX = 4096
CREDITS_MAX = 2**31 - 1
RESERVED_WORKFLOW_NAMES = {".", ".."}


class AdminCatalogService:
    def __init__(self, catalog: AdminCatalogRepository) -> None:
        self._catalog = catalog

    async def workflow_response(self, workflow_id: UUID) -> WorkflowResponse | None:
        row = await self._catalog.workflow(workflow_id)
        if row is None:
            return None
        strengths = await self._catalog.lora_strengths(workflow_id)
        return workflow_responses([row], strengths)[0]

    async def create_workflow(
        self,
        *,
        name: str,
        description: str | None,
        generation_credits: int,
        is_active: bool,
    ) -> WorkflowModel:
        name = self._workflow_name(name)
        if await self._catalog.workflow_by_name(name) is not None:
            raise WorkflowNameConflictError(name)
        return await self._catalog.create_workflow(
            name,
            self._description(description),
            self._credits(generation_credits),
            is_active,
        )

    async def update_workflow(
        self, workflow_id: UUID, changes: dict[str, object]
    ) -> WorkflowModel | None:
        values: dict[str, object] = {}
        if "description" in changes:
            values["description"] = self._description(changes["description"])
        if "generation_credits" in changes:
            values["generation_credits"] = self._credits(changes["generation_credits"])
        if "is_active" in changes:
            values["is_active"] = self._boolean(changes["is_active"])
        return await self._catalog.update_workflow(workflow_id, values)

    async def delete_workflow(self, workflow_id: UUID) -> bool:
        workflow = await self._catalog.workflow(workflow_id)
        if workflow is None:
            return False
        generations, presets = await self._catalog.workflow_history(workflow_id)
        if generations or presets:
            raise WorkflowHasHistoryError(generations, presets)
        return await self._catalog.delete_workflow(workflow_id)

    async def set_workflow_loras(
        self, workflow_id: UUID, items: Sequence[tuple[UUID, float | None]]
    ) -> bool:
        workflow = await self._catalog.workflow(workflow_id)
        if workflow is None:
            return False
        prepared: list[tuple[UUID, float | None]] = []
        for lora_id, strength in items:
            if await self._catalog.lora(lora_id) is None:
                return False
            prepared.append((lora_id, self._strength(strength)))
        await self._catalog.replace_loras(workflow_id, prepared)
        return True

    async def loras(
        self, *, query: str | None, limit: int, offset: int
    ) -> tuple[list[tuple[LoraModel, int]], int]:
        return await self._catalog.loras(query=query, limit=limit, offset=offset)

    async def lora_response(self, lora_id: UUID) -> AdminLoraItem | None:
        row = await self._catalog.lora(lora_id)
        if row is None:
            return None
        return AdminLoraItem(
            id=row.id,
            name=row.name,
            description=row.description,
            preview_urls=list(row.preview_urls or []),
            is_nsfw=bool(row.is_nsfw),
            workflow_count=await self._catalog.lora_workflow_count(lora_id),
        )

    async def create_lora(
        self,
        *,
        name: str,
        description: str | None,
        preview_urls: Sequence[str],
        is_nsfw: bool,
    ) -> LoraModel:
        name = self._lora_name(name)
        if await self._catalog.lora_by_name(name) is not None:
            raise LoraNameConflictError(name)
        return await self._catalog.create_lora(
            name,
            self._description(description),
            self._preview_urls(preview_urls),
            self._boolean(is_nsfw),
        )

    async def update_lora(
        self, lora_id: UUID, changes: dict[str, object]
    ) -> LoraModel | None:
        values: dict[str, object] = {}
        if "description" in changes:
            values["description"] = self._description(changes["description"])
        if "preview_urls" in changes:
            raw = changes["preview_urls"]
            values["preview_urls"] = (
                self._preview_urls(raw) if raw is not None else []
            )
        if "is_nsfw" in changes:
            values["is_nsfw"] = self._boolean(changes["is_nsfw"])
        return await self._catalog.update_lora(lora_id, values)

    async def delete_lora(self, lora_id: UUID) -> bool:
        lora = await self._catalog.lora(lora_id)
        if lora is None:
            return False
        used_by = await self._catalog.lora_workflow_count(lora_id)
        if used_by:
            raise LoraInUseError(used_by)
        return await self._catalog.delete_lora(lora_id)

    @staticmethod
    def _workflow_name(value: object) -> str:
        name = TextValidator.validate(
            value, min_length=1, max_length=CATALOG_NAME_MAX, strip=True
        )
        if name in RESERVED_WORKFLOW_NAMES or any(
            char in name for char in ("/", "\\", "\0")
        ):
            raise ValueError("Workflow name must be a plain identifier")
        return name

    @staticmethod
    def _lora_name(value: object) -> str:
        return TextValidator.validate(
            value, min_length=1, max_length=CATALOG_NAME_MAX, strip=True
        )

    @staticmethod
    def _description(value: object) -> str | None:
        text = TextValidator.validate(
            value, max_length=DESCRIPTION_MAX, strip=True, nullable=True
        )
        return text or None

    @staticmethod
    def _credits(value: object) -> int:
        return NumberValidator.validate_integer(
            value, min_value=0, max_value=CREDITS_MAX
        )

    @staticmethod
    def _boolean(value: object) -> bool:
        if not isinstance(value, bool):
            raise ValueError("Expected a boolean")
        return value

    @staticmethod
    def _strength(value: float | None) -> float | None:
        if value is None:
            return None
        return float(validate_lora_strength(value))

    @staticmethod
    def _preview_urls(values: Sequence[str]) -> list[str]:
        return validate_preview_urls(values)
