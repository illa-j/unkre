import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import CheckConstraint, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column, validates

from adapters.database import DatabaseManager
from adapters.database.models import (
    Base,
    LoraModel,
    TransactionModel,
    UserModel,
    WalletModel,
)
from adapters.database.repositiries import CrudRepository
from domain.enums import TransactionType
from domain.exceptions import (
    ImmutableTransactionError,
    InvalidRepositoryFieldError,
    TextValidationError,
    ValidationError,
)
from domain.validators import TextValidator
from ports import CrudRepositoryInterface


class CrudRecord(Base):
    __tablename__ = "crud_test_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(String(64), unique=True)

    __table_args__ = (
        CheckConstraint(
            "length(value) BETWEEN 1 AND 64", name="check_crud_test_value_length"
        ),
    )

    @validates("value")
    def validate_value(self, key: str, value: str) -> str:
        return TextValidator.validate(value, max_length=64)


class CrudCompositeRecord(Base):
    __tablename__ = "crud_test_composite_records"

    group_id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(String(64))


@pytest.fixture
async def manager(tmp_path) -> AsyncIterator[DatabaseManager]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'crud.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            yield DatabaseManager(session)
    finally:
        await engine.dispose()


@pytest.fixture
def repository(manager) -> CrudRepository[CrudRecord, int]:
    return CrudRepository(manager, CrudRecord)


async def test_create_and_get_typed_model(repository):
    assert isinstance(repository, CrudRepositoryInterface)
    record = await repository.create(CrudRecord(value="created"))
    assert record.id is not None
    assert isinstance(record.id, int)
    assert await repository.get(record.id) is record
    assert await repository.get(9999) is None


async def test_get_all_is_ordered_and_paginated(repository):
    for ident in (3, 1, 2):
        await repository.create(CrudRecord(id=ident, value=f"record-{ident}"))
    assert [row.id for row in await repository.get_all()] == [1, 2, 3]
    assert [row.id for row in await repository.get_all(limit=1, offset=1)] == [2]
    assert await repository.get_all(offset=100) == []


@pytest.mark.parametrize(
    "options", [{"limit": 0}, {"limit": True}, {"offset": -1}, {"offset": 1.5}]
)
async def test_invalid_pagination(repository, options):
    with pytest.raises(ValidationError):
        await repository.get_all(**options)


async def test_update_and_missing_record(repository):
    record = await repository.create(CrudRecord(value="old"))
    assert await repository.update(record.id, {"value": "new"}) is record
    assert record.value == "new"
    assert await repository.update(record.id, {}) is record
    assert await repository.update(9999, {"value": "missing"}) is None


@pytest.mark.parametrize("field", ["id", "unknown", "__dict__"])
async def test_invalid_update_fields_are_rejected_before_mutation(repository, field):
    record = await repository.create(CrudRecord(value="old"))
    with pytest.raises(InvalidRepositoryFieldError):
        await repository.update(record.id, {"value": "new", field: 10})
    assert record.value == "old"


async def test_update_preserves_attribute_validation(repository):
    record = await repository.create(CrudRecord(value="valid"))
    with pytest.raises(TextValidationError):
        await repository.update(record.id, {"value": ""})
    assert record.value == "valid"


async def test_delete_and_missing_record(repository):
    record = await repository.create(CrudRecord(value="deleted"))
    ident = record.id
    assert await repository.delete(ident) is True
    assert await repository.get(ident) is None
    assert await repository.delete(ident) is False


async def test_create_does_not_commit(manager, repository):
    record = await repository.create(CrudRecord(value="discarded"))
    ident = record.id
    await manager.rollback()
    assert await repository.get(ident) is None


async def test_update_does_not_commit(manager, repository):
    record = await repository.create(CrudRecord(value="original"))
    ident = record.id
    await manager.commit()
    await repository.update(ident, {"value": "discarded"})
    await manager.rollback()
    saved = await repository.get(ident)
    assert saved is not None
    assert saved.value == "original"


async def test_delete_does_not_commit(manager, repository):
    record = await repository.create(CrudRecord(value="original"))
    ident = record.id
    await manager.commit()
    await repository.delete(ident)
    await manager.rollback()
    assert await repository.get(ident) is not None


async def test_constraint_errors_propagate_to_transaction_owner(manager, repository):
    record = await repository.create(CrudRecord(value="unique"))
    ident = record.id
    await manager.commit()
    with pytest.raises(IntegrityError):
        await repository.create(CrudRecord(value="unique"))
    await manager.rollback()
    assert await repository.get(ident) is not None


async def test_default_uuid_id_and_server_defaults(manager):
    repository = CrudRepository[LoraModel](manager, LoraModel)
    lora = await repository.create(LoraModel(name="Style"))
    assert isinstance(lora.id, uuid.UUID)
    assert lora.created_at is not None
    assert lora.updated_at is not None
    assert lora.preview_urls == []
    assert await repository.get(lora.id) is lora
    assert await repository.update(lora.id, {"name": "Updated"}) is lora


async def test_composite_primary_key(manager):
    repository = CrudRepository[CrudCompositeRecord, tuple[int, int]](
        manager, CrudCompositeRecord
    )
    record = await repository.create(
        CrudCompositeRecord(group_id=1, item_id=2, value="created")
    )
    assert await repository.get((1, 2)) is record
    assert await repository.update((1, 2), {"value": "updated"}) is record
    assert record.value == "updated"
    for field in ("group_id", "item_id"):
        with pytest.raises(InvalidRepositoryFieldError):
            await repository.update((1, 2), {field: 3})
    assert await repository.delete((1, 2)) is True


async def test_repository_cannot_bypass_transaction_immutability(manager):
    wallet = WalletModel(user=UserModel(first_name="Test"), credits=10)
    manager.add(wallet)
    repository = CrudRepository[TransactionModel](manager, TransactionModel)
    row = await repository.create(
        TransactionModel(
            wallet=wallet,
            type=TransactionType.ADJUSTMENT,
            amount=10,
            balance_before=0,
            balance_after=10,
            idempotency_key="opening",
        )
    )
    await manager.commit()
    with pytest.raises(ImmutableTransactionError):
        await repository.update(row.id, {"description": "rewrite"})
    await manager.rollback()
