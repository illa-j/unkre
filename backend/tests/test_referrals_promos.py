from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from adapters.api.dependencies.admin import get_current_admin
from adapters.api.dependencies.settings import get_app_settings
from adapters.api.guard import configure_guard
from adapters.api.main import app as main_app
from adapters.api.middlewares import authentication_middleware
from adapters.api.routes.admin import router as admin_router
from adapters.api.routes.promo import router as promo_router
from adapters.api.routes.referral import router as referral_router
from adapters.database import DatabaseManager, DatabaseSession, db_session
from adapters.database.models import (
    Base,
    PromoCodeModel,
    PromoRedemptionModel,
    TransactionModel,
    UserModel,
    WalletModel,
)
from adapters.database.repositiries import (
    ReferralRepository,
    TransactionRepository,
    UserRepository,
    WalletRepository,
)
from adapters.security.tokens import JwtProvider
from adapters.settings import AuthSettings, Settings
from domain.entities.admin import Admin
from domain.enums import TransactionType
from domain.exceptions.referral import InvalidReferralError
from domain.services.referral import ReferralService


@pytest.fixture
async def api(tmp_path, monkeypatch):
    settings = Settings(
        AUTH_SETTINGS=AuthSettings(
            USER_INITIAL_CREDITS=15,
            REFERRAL_INVITER_CREDITS=5,
            REFERRAL_INVITEE_CREDITS=5,
        )
    )
    database = DatabaseSession(f"sqlite+aiosqlite:///{tmp_path / 'rewards.db'}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session() as session:
        users = [
            UserModel(first_name="Alice"),
            UserModel(first_name="Bob"),
            UserModel(first_name="Charlie"),
            UserModel(first_name="Blocked", is_blocked=True),
        ]
        session.add_all([WalletModel(user=user, credits=10) for user in users])
        await session.commit()
    monkeypatch.setattr(db_session, "_async_session", database.session_factory)
    app = FastAPI()
    app.middleware("http")(authentication_middleware)
    app.include_router(referral_router)
    app.include_router(promo_router)
    app.include_router(admin_router)
    app.dependency_overrides[get_current_admin] = lambda: Admin(
        id=users[0].id, username="owner", is_owner=True
    )
    app.dependency_overrides[get_app_settings] = lambda: settings
    state = SimpleNamespace(
        app=app,
        database=database,
        users=users,
        settings=settings,
        tokens=JwtProvider(settings.JWT_TOKEN_SETTINGS),
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="https://api.example",
        ) as client:
            state.client = client
            login(state)
            yield state
    finally:
        await database.dispose()


def login(api, user=0):
    api.client.cookies.clear()
    api.client.cookies.set(
        api.settings.API_SETTINGS.CLIENT_ACCESS_TOKEN_COOKIE,
        api.tokens.create_access_token(
            {"sub": str(api.users[user].id), "scope": "user"}
        ),
    )


async def balance(user_id):
    async with db_session.session_scope() as session:
        return await session.scalar(
            select(WalletModel.credits).where(WalletModel.user_id == user_id)
        )


async def create_promo(api, code="WELCOME7", credits=7, **extra):
    return await api.client.post(
        "/admins/promo-codes",
        json={"code": code, "credits": credits, **extra},
    )


async def redeem(api, code):
    return await api.client.post("/promos/redeem", json={"code": code})


def test_main_registers_referral_and_promo_routes():
    paths = main_app.openapi()["paths"]
    assert "get" in paths["/referrals"]
    assert "post" in paths["/promos/redeem"]
    assert {"post", "get"} <= paths["/admins/promo-codes"].keys()
    assert "patch" in paths["/admins/promo-codes/{promo_code_id}"]


async def test_referral_rewards_are_posted_once_after_the_first_purchase(api):
    async with db_session.session_scope() as session:
        manager = DatabaseManager(session)
        users = UserRepository(manager)
        service = ReferralService(
            ReferralRepository(manager),
            WalletRepository(manager),
            TransactionRepository(manager),
            inviter_credits=5,
            invitee_credits=5,
        )
        alice = await users.get_user(api.users[0].id)
        bob = await users.get_user(api.users[1].id)
        referral = await service.attach(alice, bob)
        again = await service.attach(alice, bob)
        assert referral is not None and again is not None
        assert referral.id == again.id
        assert referral.rewarded_at is None
        with pytest.raises(InvalidReferralError):
            await service.attach(alice, alice)
    assert await balance(api.users[0].id) == 10
    assert await balance(api.users[1].id) == 10
    async with db_session.session_scope() as session:
        service = ReferralService(
            ReferralRepository(DatabaseManager(session)),
            WalletRepository(DatabaseManager(session)),
            TransactionRepository(DatabaseManager(session)),
            inviter_credits=5,
            invitee_credits=5,
        )
        assert await service.reward_for_purchase(api.users[1].id) is True
        assert await service.reward_for_purchase(api.users[1].id) is False
    assert await balance(api.users[0].id) == 15
    assert await balance(api.users[1].id) == 15
    async with db_session.session_scope() as session:
        ledger = (await session.scalars(select(TransactionModel))).all()
        assert len(ledger) == 2
        assert all(row.type == TransactionType.ADJUSTMENT for row in ledger)
        assert {
            (row.balance_before, row.balance_after, row.amount) for row in ledger
        } == {(10, 15, 5)}


async def test_referral_stats_are_owned_and_require_login(api):
    async with db_session.session_scope() as session:
        manager = DatabaseManager(session)
        service = ReferralService(
            ReferralRepository(manager),
            WalletRepository(manager),
            TransactionRepository(manager),
            inviter_credits=5,
            invitee_credits=5,
        )
        alice = await UserRepository(manager).get_user(api.users[0].id)
        bob = await UserRepository(manager).get_user(api.users[1].id)
        await service.attach(alice, bob)
    response = await api.client.get("/referrals")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "referral_code": api.users[0].referral_code,
        "invited_count": 1,
        "credits_earned": 0,
        "referrer_credits": 5,
        "invitee_credits": 5,
        "pending_count": 1,
    }
    assert response.headers["Cache-Control"] == "no-store"
    async with db_session.session_scope() as session:
        service = ReferralService(
            ReferralRepository(DatabaseManager(session)),
            WalletRepository(DatabaseManager(session)),
            TransactionRepository(DatabaseManager(session)),
            inviter_credits=5,
            invitee_credits=5,
        )
        assert await service.reward_for_purchase(api.users[1].id) is True
    response = await api.client.get("/referrals")
    assert response.json()["credits_earned"] == 5
    assert response.json()["pending_count"] == 0
    login(api, 1)
    assert (await api.client.get("/referrals")).json()["invited_count"] == 0
    api.client.cookies.clear()
    assert (await api.client.get("/referrals")).status_code == 401


async def test_promo_admin_creates_lists_and_deactivates_codes(api):
    response = await create_promo(api)
    assert response.status_code == 201, response.text
    code = response.json()
    assert code["code"] == "WELCOME7" and code["credits"] == 7
    assert code["redeemed_count"] == 0 and code["is_active"] is True
    assert (await create_promo(api)).status_code == 409
    assert (await create_promo(api, code="bad code")).status_code == 422
    listed = await api.client.get("/admins/promo-codes")
    assert listed.status_code == 200 and [item["id"] for item in listed.json()] == [
        code["id"]
    ]
    patched = await api.client.patch(
        f"/admins/promo-codes/{code['id']}", json={"is_active": False}
    )
    assert patched.status_code == 200 and patched.json()["is_active"] is False
    assert (
        await api.client.patch(
            "/admins/promo-codes/00000000-0000-4000-8000-000000000000",
            json={"is_active": True},
        )
    ).status_code == 404


async def test_promo_redeems_once_for_balance_and_ledger(api):
    await create_promo(api, max_redemptions=2)
    response = await redeem(api, "welcome7")
    assert response.status_code == 200, response.text
    assert response.json() == {"code": "WELCOME7", "credits": 7, "balance": 17}
    assert (await redeem(api, "WELCOME7")).status_code == 409
    assert await balance(api.users[0].id) == 17
    async with db_session.session_scope() as session:
        promo = await session.scalar(select(PromoCodeModel))
        assert promo.redeemed_count == 1
        assert (
            await session.scalar(
                select(func.count()).select_from(PromoRedemptionModel)
            )
            == 1
        )
        ledger = await session.scalar(select(TransactionModel))
        assert ledger.type == TransactionType.ADJUSTMENT
        assert (ledger.balance_before, ledger.balance_after) == (10, 17)
    login(api, 1)
    assert (await redeem(api, "WELCOME7")).json()["balance"] == 17
    login(api, 2)
    assert (await redeem(api, "WELCOME7")).status_code == 409
    assert await balance(api.users[2].id) == 10


@pytest.mark.parametrize(
    "extra,status",
    [
        ({"is_active": False}, 409),
        ({"expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()}, 409),
        ({"max_redemptions": 1}, 409),
    ],
)
async def test_unavailable_promo_codes_do_not_credit(api, extra, status):
    if "max_redemptions" in extra:
        await create_promo(api, max_redemptions=1)
        login(api, 1)
        assert (await redeem(api, "WELCOME7")).status_code == 200
        login(api, 0)
    else:
        await create_promo(api, **extra)
    assert (await redeem(api, "WELCOME7")).status_code == status
    assert await balance(api.users[0].id) == 10


async def test_unknown_promo_and_blocked_user_are_rejected(api):
    assert (await redeem(api, "MISSING")).status_code == 404
    assert (await redeem(api, "bad code")).status_code == 422
    await create_promo(api)
    login(api, 3)
    assert (await redeem(api, "WELCOME7")).status_code == 403
    assert await balance(api.users[3].id) == 10


async def test_guard_requires_csrf_for_redemption_and_admin_writes(api):
    settings = api.settings
    async with db_session.session_scope() as session:
        session.add(PromoCodeModel(code="WELCOME7", credits=7))
    settings.API_SETTINGS.SECURITY_REDIS_ENABLED = False
    configure_guard(api.app, settings)
    assert (await redeem(api, "WELCOME7")).status_code == 403
    bootstrap = await api.client.get("/referrals")
    token = bootstrap.headers["X-CSRF-Token"]
    response = await api.client.post(
        "/promos/redeem",
        json={"code": "WELCOME7"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200, response.text
    assert (
        await api.client.post(
            "/admins/promo-codes",
            json={"code": "ANOTHER", "credits": 1},
        )
    ).status_code == 403
    assert (
        await api.client.post(
            "/admins/promo-codes",
            json={"code": "ANOTHER", "credits": 1},
            headers={"X-CSRF-Token": token},
        )
    ).status_code == 201
