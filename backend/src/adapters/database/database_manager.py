from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.engine import Result, ScalarResult
from sqlalchemy.ext.asyncio import AsyncSession

from ports import DatabaseManagerInterface


class DatabaseManager(DatabaseManagerInterface):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @property
    def db(self) -> AsyncSession:
        return self._db

    async def commit(self) -> None:
        await self._db.commit()

    async def rollback(self) -> None:
        await self._db.rollback()

    def add(self, instance: Any) -> None:
        self._db.add(instance)

    async def delete(self, instance: Any) -> None:
        await self._db.delete(instance)

    async def execute(self, statement: Any) -> Result[Any]:
        return await self._db.execute(statement)

    async def scalar(self, statement: Any) -> Any:
        return await self._db.scalar(statement)

    async def get(self, entity: Any, ident: Any) -> Any:
        return await self._db.get(entity, ident)

    async def scalars(self, statement: Any) -> ScalarResult[Any]:
        return await self._db.scalars(statement)

    async def refresh(
        self, instance: Any, attribute_names: Sequence[str] | None = None
    ) -> None:
        await self._db.refresh(instance, attribute_names=attribute_names)

    async def flush(self) -> None:
        await self._db.flush()
