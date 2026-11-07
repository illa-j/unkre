from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, insert, select, update

from adapters.database.models import (
    GenerationModel,
    GenerationPresetModel,
    LoraModel,
    WorkflowModel,
    workflow_loras,
)
from ports import DatabaseManagerInterface


class AdminCatalogRepository:
    """Writes and reads for the admin workflow/LoRA catalog."""

    def __init__(self, db: DatabaseManagerInterface) -> None:
        self._db = db

    async def workflow(self, workflow_id: UUID) -> WorkflowModel | None:
        return await self._db.get(WorkflowModel, workflow_id)

    async def workflow_by_name(self, name: str) -> WorkflowModel | None:
        return await self._db.scalar(
            select(WorkflowModel).where(WorkflowModel.name == name)
        )

    async def create_workflow(
        self,
        name: str,
        description: str | None,
        generation_credits: int,
        is_active: bool,
    ) -> WorkflowModel:
        row = WorkflowModel(
            name=name,
            description=description,
            generation_credits=generation_credits,
            is_active=is_active,
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        return row

    async def update_workflow(
        self, workflow_id: UUID, values: dict[str, object]
    ) -> WorkflowModel | None:
        if not values:
            return await self.workflow(workflow_id)
        row = await self._db.scalar(
            update(WorkflowModel)
            .where(WorkflowModel.id == workflow_id)
            .values(**values)
            .returning(WorkflowModel)
            .execution_options(synchronize_session=False)
        )
        return row

    async def workflow_history(self, workflow_id: UUID) -> tuple[int, int]:
        generations = await self._db.scalar(
            select(func.count(GenerationModel.id)).where(
                GenerationModel.workflow_id == workflow_id
            )
        )
        presets = await self._db.scalar(
            select(func.count(GenerationPresetModel.id)).where(
                GenerationPresetModel.workflow_id == workflow_id
            )
        )
        return int(generations or 0), int(presets or 0)

    async def delete_workflow(self, workflow_id: UUID) -> bool:
        removed = await self._db.scalar(
            delete(WorkflowModel)
            .where(WorkflowModel.id == workflow_id)
            .returning(WorkflowModel.id)
            .execution_options(synchronize_session=False)
        )
        return removed is not None

    async def lora_strengths(self, workflow_id: UUID) -> dict[tuple[UUID, UUID], float]:
        rows = await self._db.execute(
            select(
                workflow_loras.c.workflow_id,
                workflow_loras.c.lora_id,
                workflow_loras.c.recommended_strength,
            ).where(workflow_loras.c.workflow_id == workflow_id)
        )
        return {
            (wid, lora_id): float(strength)
            for wid, lora_id, strength in rows.all()
            if strength is not None
        }

    async def replace_loras(self, workflow_id: UUID, items: Sequence[tuple[UUID, float | None]]) -> None:
        await self._db.execute(
            delete(workflow_loras).where(workflow_loras.c.workflow_id == workflow_id)
        )
        for lora_id, strength in items:
            await self._db.execute(
                insert(workflow_loras).values(
                    workflow_id=workflow_id,
                    lora_id=lora_id,
                    recommended_strength=strength,
                )
            )

    async def lora(self, lora_id: UUID) -> LoraModel | None:
        return await self._db.get(LoraModel, lora_id)

    async def lora_by_name(self, name: str) -> LoraModel | None:
        return await self._db.scalar(select(LoraModel).where(LoraModel.name == name))

    async def create_lora(
        self,
        name: str,
        description: str | None,
        preview_urls: list[str],
        is_nsfw: bool,
    ) -> LoraModel:
        row = LoraModel(
            name=name,
            description=description,
            preview_urls=preview_urls,
            is_nsfw=is_nsfw,
        )
        self._db.add(row)
        await self._db.flush()
        await self._db.refresh(row)
        return row

    async def update_lora(
        self, lora_id: UUID, values: dict[str, object]
    ) -> LoraModel | None:
        if not values:
            return await self.lora(lora_id)
        row = await self._db.scalar(
            update(LoraModel)
            .where(LoraModel.id == lora_id)
            .values(**values)
            .returning(LoraModel)
            .execution_options(synchronize_session=False)
        )
        return row

    async def delete_lora(self, lora_id: UUID) -> bool:
        removed = await self._db.scalar(
            delete(LoraModel)
            .where(LoraModel.id == lora_id)
            .returning(LoraModel.id)
            .execution_options(synchronize_session=False)
        )
        return removed is not None

    async def lora_workflow_count(self, lora_id: UUID) -> int:
        return int(
            await self._db.scalar(
                select(func.count()).select_from(workflow_loras).where(
                    workflow_loras.c.lora_id == lora_id
                )
            )
            or 0
        )

    async def loras(
        self, *, query: str | None, limit: int, offset: int
    ) -> tuple[list[tuple[LoraModel, int]], int]:
        counts = (
            select(func.count())
            .select_from(workflow_loras)
            .where(workflow_loras.c.lora_id == LoraModel.id)
            .correlate(LoraModel)
            .scalar_subquery()
        )
        statement = select(LoraModel, counts.label("workflow_count")).order_by(
            LoraModel.name.asc()
        )
        total_statement = select(func.count(LoraModel.id))
        if query:
            needle = f"%{query.strip().lower()}%"
            condition = func.lower(LoraModel.name).like(needle) | func.lower(
                func.coalesce(LoraModel.description, "")
            ).like(needle)
            statement = statement.where(condition)
            total_statement = total_statement.where(condition)
        rows = (
            await self._db.execute(statement.limit(limit).offset(offset))
        ).all()
        total = int(await self._db.scalar(total_statement) or 0)
        return [(row[0], int(row[1] or 0)) for row in rows], total
