from importlib import import_module
from typing import TYPE_CHECKING, Any

from adapters.database.database_manager import DatabaseManager
from adapters.database.session import DatabaseSession

if TYPE_CHECKING:
    from adapters.database.db_session import (
        get_async_db,
        get_sync_db_session,
        session_scope,
    )


def __getattr__(name: str) -> Any:
    if name in {"get_async_db", "get_sync_db_session", "session_scope"}:
        module = import_module("adapters.database.db_session")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
