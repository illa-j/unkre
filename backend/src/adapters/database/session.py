from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseSession:
    def __init__(self, database_url: str, **engine_options: Any) -> None:
        self.engine = create_async_engine(database_url, **engine_options)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            try:
                yield session
            finally:
                await session.rollback()

    async def dispose(self) -> None:
        await self.engine.dispose()
