from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from adapters.settings import get_settings

settings = get_settings()

_async_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_SETTINGS.DATABASE_URL_ASYNC,
    pool_pre_ping=True,
    pool_size=settings.DATABASE_SETTINGS.DB_POOL_SIZE,
    max_overflow=settings.DATABASE_SETTINGS.DB_MAX_OVERFLOW,
)

_async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _async_engine,
    expire_on_commit=False,
)

_engine: Engine = create_engine(
    settings.DATABASE_SETTINGS.DATABASE_URL_SYNC,
    pool_pre_ping=True,
    pool_size=settings.DATABASE_SETTINGS.DB_POOL_SIZE,
    max_overflow=settings.DATABASE_SETTINGS.DB_MAX_OVERFLOW,
)

_session: sessionmaker[Session] = sessionmaker(
    _engine,
    expire_on_commit=False,
)


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession]:
    async with _async_session() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def get_async_db() -> AsyncGenerator[AsyncSession]:
    async with session_scope() as session:
        yield session


@contextmanager
def get_sync_db_session() -> Generator[Session]:
    with _session() as session:
        try:
            yield session
        except BaseException:
            session.rollback()
            raise
