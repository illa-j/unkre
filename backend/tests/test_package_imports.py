import os
import subprocess
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"


def run_isolated(code: str, *, configured: bool = False) -> None:
    env = {**os.environ, "PYTHONPATH": str(SOURCE_ROOT)}
    if configured:
        env.update(
            POSTGRES_HOST="localhost",
            POSTGRES_DB_PORT="5432",
            POSTGRES_USER="test",
            POSTGRES_PASSWORD="test",
            POSTGRES_DB="test",
            JWT_ALGORITHM="HS256",
            ACCESS_KEY_TIMEDELTA_MINUTES="15",
            REFRESH_KEY_TIMEDELTA_MINUTES="1440",
            SECRET_KEY_ACCESS="test-access",
            SECRET_KEY_REFRESH="test-refresh",
        )
    result = subprocess.run(
        [sys.executable, "-W", "error", "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_public_imports_do_not_construct_settings_or_engines():
    run_isolated("""
import sys
from unittest.mock import patch
from pydantic_settings import BaseSettings

with patch.object(BaseSettings, "__init__", side_effect=AssertionError("Settings constructed")), \\
     patch("sqlalchemy.create_engine", side_effect=AssertionError("Sync engine created")), \\
     patch("sqlalchemy.ext.asyncio.create_async_engine", side_effect=AssertionError("Async engine created")):
    from adapters.settings import Settings, DatabaseSettings, get_settings
    from adapters.database import DatabaseManager
    from adapters.database.repositiries import CrudRepository
    from adapters.database.models import (
        AdminModel, AdminRefreshTokenModel, Base, UserModel,
        WalletModel, PaymentModel, PaymentRefundModel, TransactionModel,
        GenerationModel, LoraModel, WorkflowModel, workflow_loras,
    )
    from domain import PaymentProvider, PaymentStatus, TransactionType
    from domain.exceptions import InvalidPaymentAmountError
    from domain.validators import PaymentAmountValidator
    from ports import CrudRepositoryInterface, DatabaseManagerInterface
    from sqlalchemy.orm import configure_mappers
    configure_mappers()
    assert issubclass(DatabaseManager, DatabaseManagerInterface)
    assert issubclass(CrudRepository, CrudRepositoryInterface)
    assert "adapters.database.db_session" not in sys.modules
    assert "admins" in Base.metadata.tables
""")


def test_settings_factory_and_legacy_import_share_one_instance():
    run_isolated(
        """
from adapters.settings import Settings, get_settings
from adapters.settings.settings import settings
assert isinstance(settings, Settings)
assert settings is get_settings()
assert get_settings() is get_settings()
assert settings.DATABASE_SETTINGS.POSTGRES_DB_PORT == 5432
""",
        configured=True,
    )


def test_database_session_exports_load_only_when_requested():
    run_isolated(
        """
import sys
import adapters.database as database
assert "adapters.database.db_session" not in sys.modules
from adapters.database import get_async_db, get_sync_db_session, session_scope
from adapters.database import db_session
assert get_async_db is db_session.get_async_db
assert get_sync_db_session is db_session.get_sync_db_session
assert session_scope is db_session.session_scope
""",
        configured=True,
    )


def test_all_source_modules_and_internal_imports_resolve():
    run_isolated(
        """
import ast
import importlib
from pathlib import Path

source_root = Path(__import__("os").environ["PYTHONPATH"])
for path in sorted(source_root.rglob("*.py")):
    # Alembic executes this script with a migration context, not as a module.
    if path.relative_to(source_root).as_posix() == "adapters/database/migrations/env.py":
        continue
    parts = list(path.relative_to(source_root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    importlib.import_module(".".join(parts))
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.ImportFrom) or node.level or not node.module:
            continue
        if node.module.split(".")[0] not in {"adapters", "domain", "ports"}:
            continue
        for alias in node.names:
            exec(f"from {node.module} import {alias.name}", {})
""",
        configured=True,
    )
