from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from sqlalchemy.engine import Result, ScalarResult
from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseManagerInterface(ABC):
    @property
    @abstractmethod
    def db(self) -> AsyncSession: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

    @abstractmethod
    def add(self, instance: Any) -> None: ...

    @abstractmethod
    async def delete(self, instance: Any) -> None: ...

    @abstractmethod
    async def execute(self, statement: Any) -> Result[Any]: ...

    @abstractmethod
    async def scalar(self, statement: Any) -> Any: ...

    @abstractmethod
    async def get(self, entity: Any, ident: Any) -> Any: ...

    @abstractmethod
    async def scalars(self, statement: Any) -> ScalarResult[Any]: ...

    @abstractmethod
    async def refresh(
        self, instance: Any, attribute_names: Sequence[str] | None = None
    ) -> None: ...

    @abstractmethod
    async def flush(self) -> None: ...
