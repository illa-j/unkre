from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from adapters.database.models import WorkflowModel, workflow_loras
from adapters.database.repositiries import CrudRepository
from domain.entities.workflow import Lora, Workflow
from ports import DatabaseManagerInterface


class WorkflowRepository(CrudRepository[WorkflowModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, WorkflowModel)

    async def get_all(
        self, *, limit: int = 100, offset: int = 0, active_only: bool = False
    ) -> list[WorkflowModel]:
        statement = select(WorkflowModel).order_by(WorkflowModel.id)
        if active_only:
            statement = statement.where(WorkflowModel.is_active.is_(True))
        rows = await self._db.scalars(
            statement.offset(offset).limit(limit)
        )
        return list(rows.unique())

    async def lora_strengths(
        self, workflow_ids: Sequence[UUID]
    ) -> dict[tuple[UUID, UUID], float]:
        if not workflow_ids:
            return {}
        rows = await self._db.execute(
            select(
                workflow_loras.c.workflow_id,
                workflow_loras.c.lora_id,
                workflow_loras.c.recommended_strength,
            ).where(workflow_loras.c.workflow_id.in_(workflow_ids))
        )
        return {
            (workflow_id, lora_id): float(strength)
            for workflow_id, lora_id, strength in rows.all()
            if strength is not None
        }

    async def get_workflow(self, workflow_id: UUID) -> Workflow | None:
        row = await self.get(workflow_id)
        # Inactive models stay in the database for history but cannot be used.
        if row is None or not row.is_active:
            return None
        return Workflow(
            id=row.id,
            name=row.name,
            description=row.description,
            generation_credits=row.generation_credits,
            loras=tuple(
                Lora(
                    id=lora.id,
                    name=lora.name,
                    description=lora.description,
                    preview_urls=tuple(lora.preview_urls),
                )
                for lora in row.loras
            ),
        )
