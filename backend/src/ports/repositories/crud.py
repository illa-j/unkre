from abc import ABC, abstractmethod
from collections.abc import Mapping
from uuid import UUID


class CrudRepositoryInterface[ModelT, IdT = UUID](ABC):
    @abstractmethod
    async def create(self, instance: ModelT) -> ModelT: ...

    @abstractmethod
    async def get(self, ident: IdT) -> ModelT | None: ...

    @abstractmethod
    async def get_all(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]: ...

    @abstractmethod
    async def update(
        self, ident: IdT, values: Mapping[str, object]
    ) -> ModelT | None: ...

    @abstractmethod
    async def delete(self, ident: IdT) -> bool: ...
