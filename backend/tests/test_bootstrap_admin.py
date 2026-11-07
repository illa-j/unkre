import pytest
from sqlalchemy import func, select

from adapters.api.bootstrap import ensure_bootstrap_admin
from adapters.database import DatabaseSession, db_session
from adapters.database.models import AdminModel, Base
from adapters.security.password_hasher import Argon2PasswordHasher
from adapters.settings import AdminSettings, Settings

PASSWORD = "bootstrap password 123"


@pytest.fixture
async def database(tmp_path, monkeypatch):
    session = DatabaseSession(f"sqlite+aiosqlite:///{tmp_path / 'bootstrap.db'}")
    async with session.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(db_session, "_async_session", session.session_factory)
    try:
        yield session
    finally:
        await session.dispose()


def settings(name: str = "owner", password: str = PASSWORD) -> Settings:
    return Settings(ADMIN_SETTINGS=AdminSettings(ADMIN_NAME=name, ADMIN_PASSWORD=password))


async def admins() -> list[AdminModel]:
    async with db_session.session_scope() as session:
        return list((await session.scalars(select(AdminModel))).all())


async def test_startup_creates_the_owner_from_env(database):
    await ensure_bootstrap_admin(settings())

    rows = await admins()
    assert len(rows) == 1
    admin = rows[0]
    assert admin.username == "owner"
    assert admin.is_owner is True
    assert admin._hashed_password != PASSWORD
    assert Argon2PasswordHasher().verify_password(PASSWORD, admin._hashed_password)


async def test_bootstrap_is_idempotent_and_keeps_the_existing_password(database):
    await ensure_bootstrap_admin(settings())
    await ensure_bootstrap_admin(settings(password="a completely different pass"))

    rows = await admins()
    assert len(rows) == 1
    assert Argon2PasswordHasher().verify_password(PASSWORD, rows[0]._hashed_password)


async def test_bootstrap_skips_without_credentials(database):
    await ensure_bootstrap_admin(Settings(ADMIN_SETTINGS=AdminSettings(ADMIN_NAME="", ADMIN_PASSWORD="")))
    await ensure_bootstrap_admin(settings(name=""))
    await ensure_bootstrap_admin(settings(password=""))

    assert await admins() == []


async def test_bootstrap_rejects_short_passwords_and_names(database):
    await ensure_bootstrap_admin(settings(password="short"))
    await ensure_bootstrap_admin(settings(name="a"))

    async with db_session.session_scope() as session:
        assert await session.scalar(select(func.count(AdminModel.id))) == 0


async def test_bootstrap_does_not_touch_a_handmade_admin(database):
    async with db_session.session_scope() as session:
        session.add(AdminModel.create("owner", "handmade password", is_owner=False))
    await ensure_bootstrap_admin(settings())

    rows = await admins()
    assert len(rows) == 1
    assert rows[0].is_owner is False
