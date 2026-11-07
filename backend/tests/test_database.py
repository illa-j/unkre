import asyncio
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from adapters.database import DatabaseSession


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(unique=True)


@pytest.fixture
async def database(tmp_path) -> AsyncIterator[DatabaseSession]:
    database = DatabaseSession(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    try:
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield database
    finally:
        await database.dispose()


async def values(database: DatabaseSession) -> list[str]:
    async with database.session() as session:
        return list(await session.scalars(select(Record.value).order_by(Record.id)))


async def test_commit_persists_and_keeps_attributes(database):
    record = Record(value="saved")
    async with database.session() as session:
        session.add(record)
        await session.commit()
        assert record.id is not None
        assert record.value == "saved"

    assert record.value == "saved"
    assert await values(database) == ["saved"]


async def test_flush_without_commit_is_rolled_back(database):
    async with database.session() as session:
        record = Record(value="discarded")
        session.add(record)
        await session.flush()
        assert record.id is not None

    assert await values(database) == []


@pytest.mark.parametrize("error", [RuntimeError, asyncio.CancelledError])
async def test_error_is_propagated_and_changes_are_rolled_back(database, error):
    with pytest.raises(error):
        async with database.session() as session:
            session.add(Record(value="discarded"))
            await session.flush()
            raise error()

    assert await values(database) == []


async def test_explicit_rollback_allows_new_transaction(database):
    async with database.session() as session:
        session.add(Record(value="discarded"))
        await session.flush()
        await session.rollback()
        session.add(Record(value="saved"))
        await session.commit()
        session.add(Record(value="also discarded"))
        await session.flush()

    assert await values(database) == ["saved"]


async def test_failed_commit_is_cleaned_up_and_next_session_can_be_used(database):
    with pytest.raises(IntegrityError):
        async with database.session() as session:
            session.add_all([Record(value="duplicate"), Record(value="duplicate")])
            await session.commit()

    assert await values(database) == []
    async with database.session() as session:
        session.add(Record(value="saved"))
        await session.commit()
    assert await values(database) == ["saved"]


async def test_separate_contexts_have_separate_sessions(database):
    async with (
        database.session() as first,
        database.session() as second,
    ):
        assert first is not second


@pytest.mark.parametrize("commit", [False, True])
async def test_direct_session_requires_explicit_commit(database, commit):
    async with database.session() as session:
        session.add(Record(value="saved"))
        await session.flush()
        if commit:
            await session.commit()

    assert await values(database) == (["saved"] if commit else [])


async def test_direct_session_rolls_back_on_error(database):
    with pytest.raises(ValueError, match="failed"):
        async with database.session() as session:
            session.add(Record(value="discarded"))
            await session.flush()
            raise ValueError("failed")

    assert await values(database) == []
