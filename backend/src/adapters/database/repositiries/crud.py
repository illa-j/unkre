from collections.abc import Mapping
from typing import cast
from uuid import UUID

from sqlalchemy import ScalarResult, inspect, select

from adapters.database.models import Base
from domain.exceptions import InvalidRepositoryFieldError
from domain.validators import NumberValidator
from ports import CrudRepositoryInterface, DatabaseManagerInterface


class CrudRepository[ModelT: Base, IdT = UUID](CrudRepositoryInterface[ModelT, IdT]):
    def __init__(self, db: DatabaseManagerInterface, model: type[ModelT]) -> None:
        self._db = db
        self._model = model

    async def create(self, instance: ModelT) -> ModelT:
        self._db.add(instance)
        await self._db.flush()
        await self._db.refresh(instance)
        return instance

    async def get(self, ident: IdT) -> ModelT | None:
        return cast(ModelT | None, await self._db.get(self._model, ident))

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        limit = NumberValidator.validate_integer(limit, min_value=1)
        offset = NumberValidator.validate_integer(offset, min_value=0)
        statement = (
            select(self._model)
            .order_by(*inspect(self._model).primary_key)
            .offset(offset)
            .limit(limit)
        )
        result: ScalarResult[ModelT] = await self._db.scalars(statement)
        return list(result.unique())

    async def update(self, ident: IdT, values: Mapping[str, object]) -> ModelT | None:
        mapper = inspect(self._model)
        primary_keys = {
            mapper.get_property_by_column(column).key for column in mapper.primary_key
        }
        for field in values:
            if field not in mapper.column_attrs:
                raise InvalidRepositoryFieldError(field, "not a mapped column")
            if field in primary_keys:
                raise InvalidRepositoryFieldError(field, "primary keys are read-only")
        instance = await self.get(ident)
        if instance is None or not values:
            return instance
        for field, value in values.items():
            setattr(instance, field, value)
        await self._db.flush()
        await self._db.refresh(instance)
        return instance

    async def delete(self, ident: IdT) -> bool:
        instance = await self.get(ident)
        if instance is None:
            return False
        await self._db.delete(instance)
        await self._db.flush()
        return True
