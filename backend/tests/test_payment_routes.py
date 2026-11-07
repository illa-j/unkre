import base64
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid7

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adapters.api.dependencies.payment import get_payment_bot, get_payment_http_client
from adapters.api.dependencies.settings import get_app_settings
from adapters.api.guard import configure_guard
from adapters.api.main import app as main_app
from adapters.api.middlewares import authentication_middleware
from adapters.api.routes.payment import router
from adapters.database import DatabaseManager, db_session
from adapters.database.models import (
    Base,
    PaymentModel,
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
from adapters.settings import PaymentSettings, Settings
from domain.enums import PaymentStatus
from domain.services.referral import ReferralService

SECRET = "test-atlos-secret"
WEBHOOK_SECRET = "test-telegram-webhook"


@pytest.fixture
async def api(tmp_path, monkeypatch):
    settings = Settings(
        PAYMENT_SETTINGS=PaymentSettings(
            CRYPTO_PRICE_PER_CREDIT=Decimal("1.25"),
            STARS_PRICE_PER_CREDIT=25,
            ATLOS_MERCHANT_ID="merchant",
            ATLOS_API_SECRET=SECRET,
            TELEGRAM_BOT_TOKEN="123456:test-token",
            TELEGRAM_WEBHOOK_SECRET=WEBHOOK_SECRET,
        )
    )
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'payment-api.db'}",
        connect_args={"autocommit": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "_async_session", factory)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with db_session.session_scope() as session:
        users = [
            UserModel(first_name="First", telegram_id=123),
            UserModel(first_name="Second", telegram_id=456),
        ]
        session.add_all([WalletModel(user=user, credits=5) for user in users])
        await session.flush()
    state = SimpleNamespace(
        settings=settings, users=users, requests=[], atlos_status=200, factory=factory
    )

    def atlos(request):
        state.requests.append(request)
        count = len(state.requests)
        return httpx.Response(
            state.atlos_status,
            json={
                "Id": f"invoice-{count}",
                "PaymentLink": f"https://atlos.io/payment/{count}",
            },
        )

    state.bot = SimpleNamespace(
        create_invoice_link=AsyncMock(return_value="https://t.me/$invoice")
    )
    test_app = FastAPI()
    state.app = test_app
    test_app.middleware("http")(authentication_middleware)
    test_app.include_router(router)
    test_app.dependency_overrides[get_app_settings] = lambda: settings
    test_app.dependency_overrides[get_payment_bot] = lambda: state.bot
    async with httpx.AsyncClient(transport=httpx.MockTransport(atlos)) as provider:
        test_app.dependency_overrides[get_payment_http_client] = lambda: provider
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=test_app, raise_app_exceptions=False),
            base_url="https://api.example",
        ) as client:
            state.client = client
            state.tokens = JwtProvider(settings.JWT_TOKEN_SETTINGS)
            login(state)
            try:
                yield state
            finally:
                await engine.dispose()


def login(api, user=0, *, scope="user"):
    api.client.cookies.clear()
    token = api.tokens.create_access_token(
        {"sub": str(api.users[user].id), "scope": scope}
    )
    api.client.cookies.set(api.settings.API_SETTINGS.CLIENT_ACCESS_TOKEN_COOKIE, token)
    return token


async def create_payment(api, provider="crypto", *, credits=4, key=None, **extra):
    return await api.client.post(
        f"/payments/{provider}",
        json={"credits": credits, "idempotency_key": key or str(uuid7()), **extra},
    )


async def read_balance(user_id):
    async with db_session.session_scope() as session:
        return await session.scalar(
            select(WalletModel.credits).where(WalletModel.user_id == user_id)
        )


def crypto_confirmation(payment):
    return {
        "MerchantId": "merchant",
        "OrderId": payment["id"],
        "OrderAmount": payment["amount"],
        "OrderCurrency": payment["currency"],
        "PaidAmount": payment["amount"],
        "TransactionId": "tx-" + payment["id"],
        "Status": 100,
        "TimeSent": datetime.now(UTC).isoformat(),
        "Asset": "USDC",
        "Blockchain": "ETH",
        "Amount": payment["amount"],
        "Fee": "0.1",
        "BlockchainHash": "hash-" + payment["id"],
        "UserWallet": "sender",
    }


def signed(data):
    body = json.dumps(data).encode()
    signature = base64.b64encode(hmac.digest(SECRET.encode(), body, "sha256")).decode()
    return body, {"Signature": signature, "Content-Type": "application/json"}


def telegram_success(payment, *, charge=None):
    return {
        "update_id": 2,
        "message": {
            "message_id": 1,
            "date": int(datetime.now(UTC).timestamp()),
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 123, "is_bot": False, "first_name": "First"},
            "successful_payment": {
                "currency": "XTR",
                "total_amount": int(Decimal(payment["amount"])),
                "invoice_payload": payment["id"],
                "telegram_payment_charge_id": charge or "charge-" + payment["id"],
                "provider_payment_charge_id": "",
            },
        },
    }


def pre_checkout(payment, *, user=123, amount=None):
    return {
        "update_id": 1,
        "pre_checkout_query": {
            "id": "query",
            "from": {"id": user, "is_bot": False, "first_name": "First"},
            "currency": "XTR",
            "total_amount": amount
            if amount is not None
            else int(Decimal(payment["amount"])),
            "invoice_payload": payment["id"],
        },
    }


def test_main_registers_payment_routes():
    paths = main_app.openapi()["paths"]
    assert {
        "/payments",
        "/payments/prices",
        "/payments/crypto",
        "/payments/stars",
        "/payments/{payment_id}",
        "/payments/webhooks/atlos",
        "/payments/webhooks/telegram",
    } <= paths.keys()


def test_payment_prices_load_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("CRYPTO_PRICE_PER_CREDIT", raising=False)
    monkeypatch.delenv("STARS_PRICE_PER_CREDIT", raising=False)
    path = tmp_path / ".env"
    path.write_text("CRYPTO_PRICE_PER_CREDIT=0.125\nSTARS_PRICE_PER_CREDIT=3\n")
    config = PaymentSettings(_env_file=path)
    assert config.CRYPTO_PRICE_PER_CREDIT == Decimal("0.125")
    assert config.STARS_PRICE_PER_CREDIT == 3
    path.write_text("CRYPTO_PRICE_PER_CREDIT=\nSTARS_PRICE_PER_CREDIT=\n")
    config = PaymentSettings(_env_file=path)
    assert config.CRYPTO_PRICE_PER_CREDIT == Decimal("0.01")
    assert config.STARS_PRICE_PER_CREDIT == 5


@pytest.mark.parametrize(
    "values",
    [
        {"CRYPTO_PRICE_PER_CREDIT": 0},
        {"CRYPTO_PRICE_PER_CREDIT": "NaN"},
        {"STARS_PRICE_PER_CREDIT": 0},
        {"STARS_PRICE_PER_CREDIT": "1.5"},
    ],
)
def test_payment_settings_reject_invalid_prices(values):
    with pytest.raises(PydanticValidationError):
        PaymentSettings(_env_file=None, **values)


async def test_routes_require_user_cookie_not_bearer_or_admin_scope(api):
    token = login(api)
    api.client.cookies.clear()
    response = await api.client.get(
        "/payments?provider=atlos", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    login(api, scope="admin")
    assert (await api.client.get("/payments/prices")).status_code == 401


@pytest.mark.parametrize(
    "provider,amount,currency",
    [("crypto", Decimal(5), "USD"), ("stars", Decimal(100), "XTR")],
)
async def test_create_uses_server_price_and_commits_before_response(
    api, provider, amount, currency
):
    response = await create_payment(api, provider)
    assert response.status_code == 201, response.text
    data = response.json()
    assert Decimal(data["amount"]) == amount and data["currency"] == currency
    assert data["credits"] == 4 and data["status"] == "pending"
    assert {
        "wallet_id",
        "idempotency_key",
        "provider_transaction_id",
        "telegram_user_id",
    }.isdisjoint(data)
    assert response.headers["cache-control"] == "no-store"
    async with db_session.session_scope() as session:
        assert (await session.get(PaymentModel, UUID(data["id"]))).checkout_url == data[
            "checkout_url"
        ]
    assert await read_balance(api.users[0].id) == 5
    if provider == "crypto":
        assert json.loads(api.requests[0].content)["OrderAmount"] == 5
    else:
        assert api.bot.create_invoice_link.call_args.kwargs["prices"][0].amount == 100


@pytest.mark.parametrize(
    "extra", [{"amount": 1}, {"stars": 1}, {"user_id": "someone"}, {"currency": "EUR"}]
)
async def test_client_cannot_override_price_payer_or_currency(api, extra):
    response = await create_payment(api, **extra)
    assert response.status_code == 422
    assert not api.requests


@pytest.mark.parametrize("credits", [0, -1, True, 1.5, "4"])
async def test_invalid_credit_quantity_rejected(api, credits):
    assert (await create_payment(api, credits=credits)).status_code == 422
    assert not api.requests


async def test_stars_payment_has_a_100_star_minimum(api):
    below = await create_payment(api, "stars", credits=3)
    assert below.status_code == 422
    assert "minimum Telegram Stars payment is 100 Stars" in below.json()["detail"]
    assert not api.bot.create_invoice_link.called

    exact = await create_payment(api, "stars", credits=4)
    assert exact.status_code == 201, exact.text
    assert Decimal(exact.json()["amount"]) == 100


async def test_crypto_payment_has_a_one_dollar_minimum(api):
    api.settings.PAYMENT_SETTINGS.CRYPTO_PRICE_PER_CREDIT = Decimal("0.1")
    below = await create_payment(api, credits=4)
    assert below.status_code == 422
    assert "minimum crypto payment is 1 USD" in below.json()["detail"]
    assert not api.requests

    exact = await create_payment(api, credits=10)
    assert exact.status_code == 201, exact.text
    assert Decimal(exact.json()["amount"]) == 1


async def test_create_idempotency_and_mismatched_retry(api):
    first = await create_payment(api, key="one")
    second = await create_payment(api, key="one")
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"] and len(api.requests) == 1
    assert (await create_payment(api, key="one", credits=5)).status_code == 409


async def test_read_and_list_only_own_payments(api):
    first = (await create_payment(api)).json()
    login(api, 1)
    second = (await create_payment(api)).json()
    response = await api.client.get("/payments?provider=atlos")
    assert [item["id"] for item in response.json()] == [second["id"]]
    assert (
        await api.client.get(f"/payments/{first['id']}?provider=atlos")
    ).status_code == 404
    assert (
        await api.client.get(f"/payments/{second['id']}?provider=telegram_stars")
    ).status_code == 404
    assert (await api.client.get("/payments?provider=atlos&limit=0")).status_code == 422
    assert (
        await api.client.get("/payments?provider=atlos&offset=-1")
    ).status_code == 422


async def test_browser_origin_is_checked_for_cookie_based_payment(api):
    response = await api.client.post(
        "/payments/crypto",
        json={"credits": 4, "idempotency_key": "x"},
        headers={"Origin": "https://untrusted.example"},
    )
    assert response.status_code == 403 and not api.requests
    response = await api.client.post(
        "/payments/crypto",
        json={"credits": 4, "idempotency_key": "x"},
        headers={"Origin": "https://api.example"},
    )
    assert response.status_code == 201


async def test_missing_prices_disable_creation_but_preserve_history(api):
    payment = (await create_payment(api)).json()
    api.settings.PAYMENT_SETTINGS.CRYPTO_PRICE_PER_CREDIT = None
    api.settings.PAYMENT_SETTINGS.STARS_PRICE_PER_CREDIT = None
    assert (await create_payment(api)).status_code == 503
    assert (await create_payment(api, "stars")).status_code == 503
    assert (
        await api.client.get(f"/payments/{payment['id']}?provider=atlos")
    ).status_code == 200
    assert (await api.client.get("/payments/prices")).json() == {
        "crypto_price_per_credit": None,
        "crypto_currency": "USD",
        "stars_price_per_credit": None,
        "crypto_min_amount": "1",
        "stars_min_amount": 100,
    }


async def test_atlos_webhook_verifies_signature_and_credits_exactly_once(api):
    payment = (await create_payment(api)).json()
    api.client.cookies.clear()
    body, headers = signed(crypto_confirmation(payment))
    response = await api.client.post("/payments/webhooks/atlos", content=body)
    assert response.status_code == 401
    response = await api.client.post(
        "/payments/webhooks/atlos", content=body + b" ", headers=headers
    )
    assert response.status_code == 401
    assert await read_balance(api.users[0].id) == 5
    for expected in (True, False):
        response = await api.client.post(
            "/payments/webhooks/atlos", content=body, headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["credited"] is expected
    assert await read_balance(api.users[0].id) == 9
    async with db_session.session_scope() as session:
        ledger = (await session.scalars(select(TransactionModel))).one()
        assert ledger.balance_before == 5 and ledger.balance_after == 9
        assert (
            await session.get(PaymentModel, UUID(payment["id"]))
        ).status == PaymentStatus.SUCCEEDED


async def test_referral_rewards_are_credited_after_the_first_successful_payment(api):
    async with db_session.session_scope() as session:
        manager = DatabaseManager(session)
        referral_service = ReferralService(
            ReferralRepository(manager),
            WalletRepository(manager),
            TransactionRepository(manager),
            inviter_credits=5,
            invitee_credits=5,
        )
        inviter = await UserRepository(manager).get_user(api.users[0].id)
        referred = await UserRepository(manager).get_user(api.users[1].id)
        await referral_service.attach(inviter, referred)

    login(api, 1)
    payment = (await create_payment(api)).json()
    api.client.cookies.clear()
    body, headers = signed(crypto_confirmation(payment))
    response = await api.client.post(
        "/payments/webhooks/atlos", content=body, headers=headers
    )
    assert response.status_code == 200, response.text
    assert await read_balance(api.users[0].id) == 10
    assert await read_balance(api.users[1].id) == 14

    async with db_session.session_scope() as session:
        referral = await ReferralRepository(DatabaseManager(session)).get_by_referred_user(
            api.users[1].id
        )
        assert referral is not None and referral.rewarded_at is not None

    # A second purchase adds credits but must not reward the referral again.
    login(api, 1)
    second = (await create_payment(api)).json()
    api.client.cookies.clear()
    body, headers = signed(crypto_confirmation(second))
    response = await api.client.post(
        "/payments/webhooks/atlos", content=body, headers=headers
    )
    assert response.status_code == 200, response.text
    assert await read_balance(api.users[0].id) == 10
    assert await read_balance(api.users[1].id) == 18


async def test_stars_webhook_authenticates_and_reserves_before_approval(api):
    payment = (await create_payment(api, "stars")).json()
    api.client.cookies.clear()
    update = pre_checkout(payment)
    assert (
        await api.client.post("/payments/webhooks/telegram", json=update)
    ).status_code == 403
    headers = {"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET}
    response = await api.client.post(
        "/payments/webhooks/telegram", json=update, headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "method": "answerPreCheckoutQuery",
        "pre_checkout_query_id": "query",
        "ok": True,
    }
    async with db_session.session_scope() as session:
        assert (
            await session.get(PaymentModel, UUID(payment["id"]))
        ).status == PaymentStatus.PROCESSING
    assert await read_balance(api.users[0].id) == 5
    for _ in range(2):
        response = await api.client.post(
            "/payments/webhooks/telegram",
            json=telegram_success(payment),
            headers=headers,
        )
        assert response.status_code == 200, response.text
    assert await read_balance(api.users[0].id) == 9
    async with db_session.session_scope() as session:
        assert (
            await session.scalar(select(func.count()).select_from(TransactionModel))
            == 1
        )


@pytest.mark.parametrize("changes", [{"user": 456}, {"amount": 1}])
async def test_invalid_stars_pre_checkout_is_declined_without_reservation(api, changes):
    payment = (await create_payment(api, "stars")).json()
    response = await api.client.post(
        "/payments/webhooks/telegram",
        json=pre_checkout(payment, **changes),
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )
    assert response.status_code == 200 and response.json()["ok"] is False
    async with db_session.session_scope() as session:
        assert (
            await session.get(PaymentModel, UUID(payment["id"]))
        ).status == PaymentStatus.PENDING
    assert await read_balance(api.users[0].id) == 5


async def test_commit_failure_never_sends_stars_checkout_approval(api, monkeypatch):
    payment = (await create_payment(api, "stars")).json()

    def failing_factory():
        session = api.factory()
        session.commit = AsyncMock(side_effect=SQLAlchemyError("commit failed"))
        return session

    monkeypatch.setattr(db_session, "_async_session", failing_factory)
    response = await api.client.post(
        "/payments/webhooks/telegram",
        json=pre_checkout(payment),
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )
    assert response.status_code == 500
    async with api.factory() as session:
        assert (
            await session.get(PaymentModel, UUID(payment["id"]))
        ).status == PaymentStatus.PENDING


async def test_provider_error_rolls_back_invoice(api):
    api.atlos_status = 503
    response = await create_payment(api)
    assert response.status_code == 503
    async with db_session.session_scope() as session:
        assert await session.scalar(select(func.count()).select_from(PaymentModel)) == 0
    assert await read_balance(api.users[0].id) == 5


@pytest.mark.parametrize("provider", ["crypto", "stars"])
async def test_guard_preserves_payment_authentication_and_signed_webhooks(
    api, provider
):
    api.settings.API_SETTINGS.SECURITY_REDIS_ENABLED = False
    configure_guard(api.app, api.settings)
    bootstrap = await api.client.get("/payments/prices")
    assert bootstrap.status_code == 200
    token = bootstrap.headers["X-CSRF-Token"]
    assert (await create_payment(api, provider)).status_code == 403
    response = await api.client.post(
        f"/payments/{provider}",
        json={"credits": 4, "idempotency_key": str(uuid7())},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 201
    payment = response.json()
    api.client.cookies.clear()
    if provider == "crypto":
        body = b"\n" + json.dumps(crypto_confirmation(payment)).encode() + b"\n"
        signature = base64.b64encode(
            hmac.digest(SECRET.encode(), body, "sha256")
        ).decode()
        invalid = await api.client.post(
            "/payments/webhooks/atlos",
            content=body,
            headers={"Signature": "invalid", "Content-Type": "application/json"},
        )
        assert invalid.status_code == 401
        for _ in range(2):
            confirmation = await api.client.post(
                "/payments/webhooks/atlos",
                content=body,
                headers={"Signature": signature, "Content-Type": "application/json"},
            )
            assert confirmation.status_code == 200
    else:
        invalid = await api.client.post(
            "/payments/webhooks/telegram", json=pre_checkout(payment)
        )
        assert invalid.status_code == 403
        headers = {"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET}
        approval = await api.client.post(
            "/payments/webhooks/telegram", json=pre_checkout(payment), headers=headers
        )
        assert approval.status_code == 200
        assert approval.json()["ok"] is True
        update = telegram_success(payment)
        update["message"]["from"]["first_name"] = "<script>alert(1)</script>"
        for _ in range(2):
            confirmation = await api.client.post(
                "/payments/webhooks/telegram", json=update, headers=headers
            )
            assert confirmation.status_code == 200
    assert await read_balance(api.users[0].id) == 9
    async with db_session.session_scope() as session:
        assert (
            await session.scalar(select(func.count()).select_from(TransactionModel))
            == 1
        )
