from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from adapters.database import DatabaseManager, session_scope


async def get_database_manager() -> AsyncIterator[DatabaseManager]:
    async with session_scope() as session:
        yield DatabaseManager(session)


DatabaseManagerDep = Annotated[
    DatabaseManager, Depends(get_database_manager, scope="function")
]
