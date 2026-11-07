from uuid import UUID

from sqlalchemy import delete, select

from adapters.database.models import SystemSettingModel
from domain.entities.system_setting import SystemSetting
from ports import DatabaseManagerInterface
from ports.repositories.system_setting import SystemSettingRepositoryInterface


class SystemSettingRepository(SystemSettingRepositoryInterface):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        self._db = db

    async def get(self, key: str) -> SystemSetting | None:
        row = await self._db.scalar(
            select(SystemSettingModel).where(SystemSettingModel.key == key)
        )
        return row.to_entity() if row is not None else None

    async def list(self) -> list[SystemSetting]:
        rows = await self._db.scalars(
            select(SystemSettingModel).order_by(SystemSettingModel.key)
        )
        return [row.to_entity() for row in rows]

    async def upsert(
        self,
        key: str,
        *,
        value: object,
        description: str | None,
        updated_by: UUID | None,
    ) -> SystemSetting:
        row = await self._db.scalar(
            select(SystemSettingModel)
            .where(SystemSettingModel.key == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            row = SystemSettingModel(
                key=key,
                value=value,
                description=description,
                updated_by=updated_by,
            )
            self._db.add(row)
        else:
            row.value = value
            row.description = description
            row.updated_by = updated_by
        await self._db.flush()
        await self._db.refresh(row)
        return row.to_entity()

    async def delete(self, key: str) -> bool:
        removed = await self._db.scalar(
            delete(SystemSettingModel)
            .where(SystemSettingModel.key == key)
            .returning(SystemSettingModel.key)
            .execution_options(synchronize_session=False)
        )
        return removed is not None
