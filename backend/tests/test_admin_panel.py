from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from adapters.api.dependencies.settings import get_app_settings
from adapters.api.middlewares import authentication_middleware
from adapters.api.routes.admin import router as admin_router
from adapters.api.routes.admin_panel import router as panel_router
from adapters.database import DatabaseSession, db_session
from adapters.database.models import (
    AdminModel,
    Base,
    GenerationModel,
    PaymentModel,
    PromoCodeModel,
    PromoRedemptionModel,
    TransactionModel,
    UserModel,
    WalletModel,
    WorkflowModel,
)
from adapters.security.password_hasher import Argon2PasswordHasher
from adapters.security.tokens import JwtProvider
from adapters.settings import ApiSettings, DatabaseSettings, JwtTokenSettings, Settings
from domain.enums import (
    GenerationStatus,
    PaymentProvider,
    PaymentStatus,
    TransactionType,
)

PASSWORD = "admin password for tests"


@pytest.fixture
async def panel(tmp_path, monkeypatch):
    settings = Settings(
        DATABASE_SETTINGS=DatabaseSettings(
            POSTGRES_HOST="localhost",
            POSTGRES_DB_PORT=5432,
            POSTGRES_USER="test",
            POSTGRES_PASSWORD="test",
            POSTGRES_DB="test",
        ),
        API_SETTINGS=ApiSettings(CSRF_ENABLED=False, SECURITY_REDIS_ENABLED=False),
        JWT_TOKEN_SETTINGS=JwtTokenSettings(
            JWT_ALGORITHM="HS256",
            ACCESS_KEY_TIMEDELTA_MINUTES=30,
            REFRESH_KEY_TIMEDELTA_MINUTES=120,
            SECRET_KEY_ACCESS="panel-access-" + "a" * 32,
            SECRET_KEY_REFRESH="panel-refresh-" + "b" * 32,
        ),
    )
    database = DatabaseSession(f"sqlite+aiosqlite:///{tmp_path / 'panel.db'}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    admin_hash = Argon2PasswordHasher().hash_password(PASSWORD)
    async with database.session() as session:
        owner = AdminModel(username="owner", _hashed_password=admin_hash, is_owner=True)
        staff = AdminModel(username="staff", _hashed_password=admin_hash, is_owner=False)
        workflow = WorkflowModel(name="Krea 2 Turbo", generation_credits=2)
        alice = UserModel(first_name="Alice", username="alice", google_email="alice@example.com")
        bob = UserModel(first_name="Bob", username="bob", is_blocked=True)
        session.add_all([owner, staff, workflow, alice, bob])
        await session.flush()
        wallet_a = WalletModel(user_id=alice.id, credits=40)
        wallet_b = WalletModel(user_id=bob.id, credits=3)
        session.add_all([wallet_a, wallet_b])
        await session.flush()
        session.add_all(
            [
                GenerationModel(
                    user_id=alice.id,
                    workflow_id=workflow.id,
                    prompt="A quiet portrait",
                    status=GenerationStatus.COMPLETED,
                    credits_spent=2,
                    runpod_job_id="job-1",
                ),
                GenerationModel(
                    user_id=bob.id,
                    workflow_id=workflow.id,
                    prompt="A loud street",
                    status=GenerationStatus.FAILED,
                    credits_spent=2,
                    runpod_job_id="job-2",
                    error="provider error",
                ),
                TransactionModel(
                    wallet_id=wallet_a.id,
                    type=TransactionType.SPEND,
                    amount=-2,
                    balance_before=42,
                    balance_after=40,
                    idempotency_key="spend-1",
                ),
                PaymentModel(
                    wallet_id=wallet_a.id,
                    provider=PaymentProvider.TELEGRAM_STARS,
                    status=PaymentStatus.SUCCEEDED,
                    credits=100,
                    amount=Decimal("500"),
                    paid_amount=Decimal("500"),
                    currency="XTR",
                    idempotency_key="payment-1",
                    provider_transaction_id="tx-1",
                    paid_at=datetime.now(UTC) - timedelta(days=2),
                ),
                PaymentModel(
                    wallet_id=wallet_b.id,
                    provider=PaymentProvider.TELEGRAM_STARS,
                    status=PaymentStatus.PENDING,
                    credits=50,
                    amount=Decimal("250"),
                    currency="XTR",
                    idempotency_key="payment-2",
                ),
            ]
        )
        promo = PromoCodeModel(code="WELCOME", credits=10, is_active=True)
        session.add(promo)
        await session.flush()
        session.add(PromoRedemptionModel(promo_code_id=promo.id, user_id=alice.id, credits=10))
        await session.commit()

    monkeypatch.setattr(db_session, "_async_session", database.session_factory)
    app = FastAPI()
    app.middleware("http")(authentication_middleware)
    app.include_router(admin_router)
    app.include_router(panel_router)
    app.dependency_overrides[get_app_settings] = lambda: settings
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://api.example"
        ) as client:
            yield SimpleNamespace(
                client=client,
                app=app,
                settings=settings,
                tokens=JwtProvider(settings.JWT_TOKEN_SETTINGS),
                admin_id=owner.id,
                staff_id=staff.id,
                alice=alice.id,
                bob=bob.id,
            )
    finally:
        await database.dispose()


async def login(panel, username="owner"):
    response = await panel.client.post(
        "/admins/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    token = response.cookies[panel.settings.API_SETTINGS.ADMIN_ACCESS_TOKEN_COOKIE]
    panel.client.cookies.set(
        panel.settings.API_SETTINGS.ADMIN_ACCESS_TOKEN_COOKIE, token
    )
    return token


async def test_overview_reports_account_activity(panel):
    await login(panel)

    response = await panel.client.get("/admins/overview")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["users_total"] == 2
    assert data["users_blocked"] == 1
    assert data["generations_total"] == 2
    assert data["generations_by_status"] == {"completed": 1, "failed": 1}
    assert data["credits_spent_24h"] == 2
    assert data["revenue_total"] == "500.00"
    assert data["payments_pending"] == 1
    assert data["promo_redemptions"] == 1
    assert len(data["daily"]) == 14
    assert sum(point["generations"] for point in data["daily"]) == 2


async def test_admin_panel_requires_an_admin_session(panel):
    for path in ("/admins/overview", "/admins/users", "/admins/generations", "/admins/payments"):
        assert (await panel.client.get(path)).status_code == 401


async def test_users_can_be_searched_and_blocked(panel):
    await login(panel)

    page = (await panel.client.get("/admins/users?query=alice")).json()
    assert page["total"] == 1
    assert page["items"][0]["username"] == "alice"
    assert page["items"][0]["credits"] == 40
    assert page["items"][0]["generations"] == 1
    assert page["items"][0]["credits_spent"] == 2

    blocked = await panel.client.get("/admins/users?state=blocked")
    assert [item["username"] for item in blocked.json()["items"]] == ["bob"]

    response = await panel.client.patch(
        f"/admins/users/{panel.alice}", json={"is_blocked": True}
    )
    assert response.status_code == 200
    assert response.json() == {"user_id": str(panel.alice), "is_blocked": True}

    assert (await panel.client.patch(f"/admins/users/{'0'*8}-0000-0000-0000-000000000000", json={"is_blocked": True})).status_code == 404


async def test_manual_credit_adjustment_posts_a_ledger_entry(panel):
    await login(panel)

    response = await panel.client.post(
        f"/admins/users/{panel.alice}/credits",
        json={"amount": 25, "description": "Support compensation"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["credits"] == 65
    page = (await panel.client.get("/admins/users?query=alice")).json()
    assert page["items"][0]["credits"] == 65

    rejected = await panel.client.post(
        f"/admins/users/{panel.alice}/credits", json={"amount": 0, "description": "Nope"}
    )
    assert rejected.status_code == 422


async def test_generations_and_payments_can_be_filtered(panel):
    await login(panel)

    generations = (await panel.client.get("/admins/generations?state=failed")).json()
    assert generations["total"] == 1
    assert generations["items"][0]["user_name"] == "Bob"
    assert generations["items"][0]["workflow"] == "Krea 2 Turbo"
    assert generations["items"][0]["error"] == "provider error"

    search = (await panel.client.get("/admins/generations?query=quiet")).json()
    assert [item["prompt"] for item in search["items"]] == ["A quiet portrait"]

    payments = (await panel.client.get("/admins/payments?state=succeeded")).json()
    assert payments["total"] == 1
    assert payments["items"][0]["amount"] == "500.00"
    assert payments["items"][0]["user_name"] == "Alice"

    pending = (await panel.client.get("/admins/payments?state=pending&provider=telegram_stars")).json()
    assert pending["total"] == 1


async def test_promo_redemptions_are_listed(panel):
    await login(panel)
    codes = (await panel.client.get("/admins/promo-codes")).json()
    response = await panel.client.get(
        f"/admins/promo-codes/{codes[0]['id']}/redemptions"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["user_email"] == "alice@example.com"


async def test_only_owners_manage_the_team(panel):
    owner_token = await login(panel)
    team = await panel.client.get("/admins/team")
    assert team.status_code == 200
    assert {item["username"] for item in team.json()["items"]} == {"owner", "staff"}

    created = await panel.client.post(
        "/admins/team",
        json={"username": "operator", "password": "another strong password", "is_owner": False},
    )
    assert created.status_code == 201, created.text
    assert created.json()["username"] == "operator"

    duplicate = await panel.client.post(
        "/admins/team",
        json={"username": "operator", "password": "another strong password"},
    )
    assert duplicate.status_code == 409

    panel.client.cookies.set(
        panel.settings.API_SETTINGS.ADMIN_ACCESS_TOKEN_COOKIE,
        panel.tokens.create_access_token(
            {"sub": str(panel.staff_id), "scope": "admin"}
        ),
    )
    assert (await panel.client.get("/admins/team")).status_code == 403
    assert owner_token


async def test_openapi_exposes_the_admin_panel(panel):
    paths = panel.app.openapi()["paths"]
    assert {
        "/admins/overview",
        "/admins/users",
        "/admins/users/{user_id}",
        "/admins/users/{user_id}/credits",
        "/admins/generations",
        "/admins/payments",
        "/admins/promo-codes/{promo_code_id}/redemptions",
        "/admins/team",
    } <= paths.keys()
