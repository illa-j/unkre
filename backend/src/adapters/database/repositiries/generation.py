from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import lazyload

from adapters.database.models import GenerationModel
from adapters.database.repositiries import CrudRepository
from domain.entities.generation import Generation
from domain.enums import GenerationStatus
from ports import DatabaseManagerInterface

ACTIVE_GENERATION_STATUSES = (
    GenerationStatus.PENDING,
    GenerationStatus.QUEUED,
    GenerationStatus.PROCESSING,
)
TERMINAL_GENERATION_STATUSES = (
    GenerationStatus.COMPLETED,
    GenerationStatus.FAILED,
    GenerationStatus.CANCELLED,
    GenerationStatus.TIMED_OUT,
)


class GenerationRepository(CrudRepository[GenerationModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, GenerationModel)

    async def create_generation(self, generation: Generation) -> Generation:
        row = await self.create(GenerationModel.from_entity(generation))
        return row.to_entity()

    async def get_generation(self, generation_id: UUID) -> Generation | None:
        row = await self.get(generation_id)
        return row.to_entity() if row is not None else None

    async def get_generations(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[Generation]:
        return [
            row.to_entity() for row in await self.get_all(limit=limit, offset=offset)
        ]

    async def update_generation(
        self, generation_id: UUID, values: Mapping[str, object]
    ) -> Generation | None:
        changes = dict(values)
        if "loras_strength" in changes:
            changes["loras_strength"] = {
                str(ident): strength
                for ident, strength in changes["loras_strength"].items()
            }
        row = await self.update(generation_id, changes)
        return row.to_entity() if row is not None else None

    async def delete_generation(self, generation_id: UUID) -> bool:
        return await self.delete(generation_id)

    async def get_expired_for_update(self, before: datetime) -> GenerationModel | None:
        finished = func.coalesce(
            GenerationModel.completed_at, GenerationModel.updated_at
        )
        return await self._db.scalar(
            select(GenerationModel)
            .options(lazyload("*"))
            .where(
                GenerationModel.status.in_(TERMINAL_GENERATION_STATUSES),
                finished <= before,
            )
            .order_by(finished, GenerationModel.id)
            .limit(1)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )

    async def delete_expired(self, ident: UUID, before: datetime) -> bool:
        removed = await self._db.scalar(
            delete(GenerationModel)
            .where(
                GenerationModel.id == ident,
                GenerationModel.status.in_(TERMINAL_GENERATION_STATUSES),
                func.coalesce(GenerationModel.completed_at, GenerationModel.updated_at)
                <= before,
            )
            .returning(GenerationModel.id)
            .execution_options(synchronize_session=False)
        )
        return removed is not None

    async def existing_ids(self, identifiers: list[UUID]) -> set[UUID]:
        if not identifiers:
            return set()
        return set(
            await self._db.scalars(
                select(GenerationModel.id).where(GenerationModel.id.in_(identifiers))
            )
        )

    async def get_for_user(
        self, user_id: UUID, generation_id: UUID
    ) -> Generation | None:
        row = await self._db.scalar(
            select(GenerationModel).where(
                GenerationModel.id == generation_id, GenerationModel.user_id == user_id
            )
        )
        return row.to_entity() if row is not None else None

    async def list_for_user(
        self, user_id: UUID, *, limit: int, offset: int
    ) -> list[Generation]:
        rows = await self._db.scalars(
            select(GenerationModel)
            .where(GenerationModel.user_id == user_id)
            .order_by(GenerationModel.created_at.desc(), GenerationModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [row.to_entity() for row in rows]

    async def delete_for_user(self, user_id: UUID, generation_id: UUID) -> bool:
        removed = await self._db.scalar(
            delete(GenerationModel)
            .where(
                GenerationModel.id == generation_id, GenerationModel.user_id == user_id
            )
            .returning(GenerationModel.id)
            .execution_options(synchronize_session=False)
        )
        return removed is not None

    async def get_for_polling(self, ident: UUID) -> GenerationModel | None:
        return await self._db.scalar(
            select(GenerationModel)
            .options(lazyload("*"))
            .where(
                GenerationModel.id == ident,
                GenerationModel.status.in_(ACTIVE_GENERATION_STATUSES),
                GenerationModel.runpod_job_id.is_not(None),
            )
        )

    async def get_active_batch(
        self, *, after: UUID | None = None, limit: int = 500
    ) -> list[GenerationModel]:
        statement = (
            select(GenerationModel)
            .options(lazyload("*"))
            .where(
                GenerationModel.status.in_(ACTIVE_GENERATION_STATUSES),
                GenerationModel.runpod_job_id.is_not(None),
            )
            .order_by(GenerationModel.id)
            .limit(limit)
        )
        if after is not None:
            statement = statement.where(GenerationModel.id > after)
        return list(await self._db.scalars(statement))

    async def apply_runpod_status(
        self,
        generation: GenerationModel,
        status: GenerationStatus,
        *,
        error: str | None,
        now: datetime,
    ) -> datetime | None:
        terminal = status not in ACTIVE_GENERATION_STATUSES
        # A concurrent poll or cancellation must not be overwritten by this response.
        return await self._db.scalar(
            update(GenerationModel)
            .where(
                GenerationModel.id == generation.id,
                GenerationModel.runpod_job_id == generation.runpod_job_id,
                GenerationModel.runpod_endpoint_id == generation.runpod_endpoint_id,
                GenerationModel.updated_at <= generation.updated_at,
                GenerationModel.status.in_(ACTIVE_GENERATION_STATUSES),
            )
            .values(
                status=status,
                error=error[:4096] if error is not None else None,
                completed_at=now if terminal else None,
                updated_at=now,
            )
            .returning(GenerationModel.updated_at)
            .execution_options(synchronize_session=False)
        )
