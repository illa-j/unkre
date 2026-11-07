import asyncio
from contextlib import asynccontextmanager
from importlib import import_module

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from adapters.database import DatabaseManager


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "session_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(unique=True)


@pytest.fixture
def sessions(monkeypatch):
    # Імпорт конфігурації не потребує справжніх облікових даних або PostgreSQL.
    for name, value in {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_DB_PORT": "5432",
        "POSTGRES_USER": "test",
        "POSTGRES_PASSWORD": "test",
        "POSTGRES_DB": "test",
        "JWT_ALGORITHM": "HS256",
        "ACCESS_KEY_TIMEDELTA_MINUTES": "15",
        "REFRESH_KEY_TIMEDELTA_MINUTES": "1440",
        "SECRET_KEY_ACCESS": "test-access",
        "SECRET_KEY_REFRESH": "test-refresh",
    }.items():
        monkeypatch.setenv(name, value)
    return import_module("adapters.database.db_session")


@pytest.fixture
async def async_database(sessions, monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'async.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(sessions, "_async_session", factory)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.parametrize("dependency", [False, True])
async def test_async_commit_and_manager(sessions, async_database, dependency):
    scope = (
        asynccontextmanager(sessions.get_async_db)
        if dependency
        else sessions.session_scope
    )
    async with scope() as session:
        manager = DatabaseManager(session)
        record = Record(value="saved")
        manager.add(record)
        await manager.flush()
        record_id = record.id
        assert manager.db is session
        assert await manager.get(Record, record.id) is record
        await manager.refresh(record, ["value"])
        result = await manager.execute(select(Record))
        assert result.scalar_one() is record
        assert (await manager.scalars(select(Record.value))).all() == ["saved"]
        assert await manager.scalar(select(Record.value)) == "saved"

    async with async_database() as session:
        assert (await session.scalars(select(Record.value))).all() == ["saved"]
        manager = DatabaseManager(session)
        record = await manager.get(Record, record_id)
        await manager.delete(record)
        await manager.rollback()
        assert await manager.get(Record, record_id) is not None
        await manager.delete(record)
        await manager.commit()
    async with async_database() as session:
        assert (await session.scalars(select(Record))).all() == []


@pytest.mark.parametrize("error", [RuntimeError, asyncio.CancelledError])
@pytest.mark.parametrize("dependency", [False, True])
async def test_async_rollback(sessions, async_database, error, dependency):
    scope = (
        asynccontextmanager(sessions.get_async_db)
        if dependency
        else sessions.session_scope
    )
    with pytest.raises(error):
        async with scope() as session:
            session.add(Record(value="discarded"))
            await session.flush()
            raise error()
    async with async_database() as session:
        assert (await session.scalars(select(Record))).all() == []


async def test_failed_commit_rolls_back(sessions, async_database):
    with pytest.raises(IntegrityError):
        async with sessions.session_scope() as session:
            session.add_all([Record(value="duplicate"), Record(value="duplicate")])
    async with sessions.session_scope() as session:
        session.add(Record(value="saved"))
    async with async_database() as session:
        assert (await session.scalars(select(Record.value))).all() == ["saved"]


@pytest.mark.parametrize("commit", [False, True])
def test_sync_requires_explicit_commit(sessions, monkeypatch, tmp_path, commit):
    engine = create_engine(f"sqlite:///{tmp_path / 'sync.db'}")
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(sessions, "_session", factory)
    try:
        Base.metadata.create_all(engine)
        with sessions.get_sync_db_session() as session:
            session.add(Record(value="saved"))
            session.flush()
            if commit:
                session.commit()
        with factory() as session:
            assert session.scalars(select(Record.value)).all() == (
                ["saved"] if commit else []
            )
    finally:
        engine.dispose()
