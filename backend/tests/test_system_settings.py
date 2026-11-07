from decimal import Decimal

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adapters.api.dependencies.admin import get_current_admin
from adapters.api.routes.admin_settings import router
from adapters.database import DatabaseManager, db_session
from adapters.database.models import AdminModel, Base
from adapters.database.repositiries import SystemSettingRepository
from domain.entities.admin import Admin
from domain.entities.system_setting import SystemSettingDefaults
from domain.exceptions.system_setting import (
    InvalidSystemSettingError,
    UnknownSystemSettingError,
)
from domain.services.system_setting import SystemSettingsService


def defaults() -> SystemSettingDefaults:
    return SystemSettingDefaults(
        initial_credits=15,
        inviter_credits=5,
        invitee_credits=5,
        crypto_price_per_credit="0.5",
        crypto_currency="USD",
        stars_price_per_credit=5,
        crypto_min_amount="1",
        stars_min_amount=100,
    )


@pytest.fixture
async def data(tmp_path, monkeypatch):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'system-settings.db'}"
    )

    @event.listens_for(engine.sync_engine, "connect")
    def setup_connection(connection, record):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine.sync_engine, "begin")
    def begin(connection):
        connection.exec_driver_sql("BEGIN")

    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "_async_session", factory)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with db_session.session_scope() as session:
        admin = AdminModel(username="admin", _hashed_password="x")
        session.add(admin)
        await session.flush()

    def service(session):
        return SystemSettingsService(
            SystemSettingRepository(DatabaseManager(session)), defaults()
        )

    try:
        yield engine, admin, service
    finally:
        await engine.dispose()


async def test_defaults_are_visible_and_overrides_are_typed(data):
    _, admin, service = data
    async with db_session.session_scope() as session:
        settings = await service(session).get_all()
        assert len(settings) == 8
        inviter = next(item for item in settings if item.key == "referral.inviter_credits")
        assert inviter.value == 5 and inviter.source == "default"

        updated = await service(session).update(
            "referral.inviter_credits", 3, admin_id=admin.id
        )
        assert updated.value == 3 and updated.source == "database"
        assert updated.updated_by == admin.id
        assert await service(session).get_int("referral.inviter_credits") == 3

        reset = await service(session).reset("referral.inviter_credits")
        assert reset.value == 5 and reset.source == "default"
        assert await service(session).get_int("referral.inviter_credits") == 5


async def test_decimal_and_currency_settings_are_normalized(data):
    _, _, service = data
    async with db_session.session_scope() as session:
        settings = service(session)
        await settings.update("payments.crypto_price_per_credit", "1.25")
        assert await settings.get_decimal("payments.crypto_price_per_credit") == Decimal(
            "1.25"
        )
        await settings.update("payments.crypto_price_per_credit", None)
        assert await settings.get_decimal("payments.crypto_price_per_credit") is None
        await settings.update("payments.crypto_currency", "eur")
        assert await settings.get_str("payments.crypto_currency") == "EUR"
        await settings.update("payments.crypto_min_amount", "2.5")
        assert await settings.get_decimal("payments.crypto_min_amount") == Decimal(
            "2.5"
        )
        await settings.update("payments.stars_min_amount", 250)
        assert await settings.get_int("payments.stars_min_amount") == 250


async def test_invalid_and_unknown_settings_are_rejected(data):
    _, _, service = data
    async with db_session.session_scope() as session:
        with pytest.raises(InvalidSystemSettingError):
            await service(session).update("referral.inviter_credits", -1)
        with pytest.raises(InvalidSystemSettingError):
            await service(session).update("payments.crypto_price_per_credit", "0")
        with pytest.raises(UnknownSystemSettingError):
            await service(session).update("missing.key", 1)


async def test_admin_settings_route_lists_and_updates(data):
    _, admin, _ = data
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_admin] = lambda: Admin(
        id=admin.id, username="admin"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example"
    ) as client:
        listed = await client.get("/admins/settings")
        assert listed.status_code == 200
        assert any(item["key"] == "referral.inviter_credits" for item in listed.json())

        updated = await client.patch(
            "/admins/settings/referral.inviter_credits", json={"value": 2}
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["value"] == 2
        assert updated.json()["source"] == "database"
