import base64
import hmac
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid7

import httpx
import pytest
from aiogram.types import (
    Chat,
    Message,
    PreCheckoutQuery,
    StarTransaction,
    StarTransactions,
    SuccessfulPayment,
    TransactionPartnerUser,
    User,
)
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adapters.database import DatabaseManager, db_session
from adapters.database.models import (
    Base,
    PaymentModel,
    TransactionModel,
    UserModel,
    WalletModel,
)
from adapters.database.repositiries import (
    PaymentRepository,
    TransactionRepository,
    UserRepository,
    WalletRepository,
)
from domain.enums import PaymentStatus, TransactionType
from domain.exceptions import ValidationError
from domain.exceptions.auth import UserBlockedError
from domain.exceptions.payments import InvalidPaymentStateError, PaymentProviderError
from domain.services import CryptoPaymentService, TelegramStarsPaymentService
from tests.test_package_imports import run_isolated

SECRET = "test-atlos-secret"
MERCHANT = "test-merchant"


@pytest.fixture
async def payments(tmp_path, monkeypatch):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'services.db'}",
        connect_args={"autocommit": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "_async_session", factory)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with db_session.session_scope() as session:
        users = [
            UserModel(first_name="First", telegram_id=123),
            UserModel(first_name="Second", telegram_id=456),
            UserModel(first_name="Google", google_sub="google"),
            UserModel(first_name="Blocked", telegram_id=789, is_blocked=True),
        ]
        for user in users:
            session.add(WalletModel(user=user, credits=5))
        await session.flush()
    state = SimpleNamespace(users=users, requests=[], transactions=[], response=None)

    def handler(request):
        state.requests.append(request)
        if state.response is not None:
            return state.response
        if request.url.path.endswith("Invoice/Create"):
            count = len(state.requests)
            return httpx.Response(
                200,
                json={
                    "Id": f"invoice-{count}",
                    "PaymentLink": f"https://atlos.io/payment/{count}",
                },
            )
        params = json.loads(request.content)
        return httpx.Response(
            200,
            content=json.dumps(
                {
                    "TotalCount": len(state.transactions),
                    "Transactions": state.transactions[
                        params["Skip"] : params["Skip"] + params["Take"]
                    ],
                },
                default=str,
            ),
        )

    state.bot = SimpleNamespace(
        create_invoice_link=AsyncMock(return_value="https://t.me/$invoice"),
        get_star_transactions=AsyncMock(return_value=StarTransactions(transactions=[])),
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        state.crypto = lambda session, **kwargs: CryptoPaymentService(
            PaymentRepository(DatabaseManager(session)),
            WalletRepository(DatabaseManager(session)),
            TransactionRepository(DatabaseManager(session)),
            UserRepository(DatabaseManager(session)),
            http,
            merchant_id=MERCHANT,
            api_secret=SECRET,
            **kwargs,
        )
        state.stars = lambda session: TelegramStarsPaymentService(
            PaymentRepository(DatabaseManager(session)),
            WalletRepository(DatabaseManager(session)),
            TransactionRepository(DatabaseManager(session)),
            UserRepository(DatabaseManager(session)),
            state.bot,
        )
        try:
            yield state
        finally:
            await engine.dispose()


async def invoice(payments, provider="crypto", *, user=0, **overrides):
    values = {"credits": 20, "idempotency_key": str(uuid7())}
    values.update({"amount": Decimal(10)} if provider == "crypto" else {"stars": 50})
    values.update(overrides)
    async with db_session.session_scope() as session:
        service = getattr(payments, provider)(session)
        return await service.create_invoice(payments.users[user].id, **values)


def transaction(payment, **overrides):
    data = {
        "MerchantId": MERCHANT,
        "OrderId": str(payment.id),
        "OrderAmount": 10,
        "OrderCurrency": "USD",
        "PaidAmount": 10,
        "TransactionId": "tx-" + str(payment.id),
        "Status": 100,
        "TimeSent": datetime.now(UTC).isoformat(),
        "Asset": "USDC",
        "Blockchain": "ETH",
        "Amount": 10,
        "Fee": "0.1",
        "BlockchainHash": "hash-" + str(payment.id),
        "UserWallet": "sender",
    }
    data.update(overrides)
    return data


def signed(data):
    body = json.dumps(data, default=str).encode()
    signature = base64.b64encode(hmac.digest(SECRET.encode(), body, "sha256")).decode()
    return body, signature


def message(payment, *, user=123, **overrides):
    data = dict(
        currency="XTR",
        total_amount=50,
        invoice_payload=str(payment.id),
        telegram_payment_charge_id="charge-" + str(payment.id),
        provider_payment_charge_id="",
    )
    data.update(overrides)
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=user, type="private"),
        from_user=User(id=user, is_bot=False, first_name="Test"),
        successful_payment=SuccessfulPayment(**data),
    )


def checkout(payment, *, user=123, **overrides):
    data = dict(
        id="checkout-id",
        from_user=User(id=user, is_bot=False, first_name="Test"),
        currency="XTR",
        total_amount=50,
        invoice_payload=str(payment.id),
    )
    data.update(overrides)
    return PreCheckoutQuery(**data)


async def balance(user_id):
    async with db_session.session_scope() as session:
        return await session.scalar(
            select(WalletModel.credits).where(WalletModel.user_id == user_id)
        )


def test_payment_services_import_without_adapters():
    run_isolated("""
import importlib.abc
import sys

class RejectAdapters(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "adapters" or fullname.startswith("adapters."):
            raise AssertionError(f"Domain services imported {fullname}")

sys.meta_path.insert(0, RejectAdapters())
from domain.services import CryptoPaymentService, TelegramStarsPaymentService
from domain.services.payment import PaymentService
assert not any(name == "adapters" or name.startswith("adapters.") for name in sys.modules)
""")


@pytest.mark.parametrize("provider", ["crypto", "stars"])
async def test_invoice_is_idempotent_and_does_not_credit_wallet(payments, provider):
    first = await invoice(payments, provider, idempotency_key="same")
    second = await invoice(payments, provider, idempotency_key="same")
    assert first.id == second.id
    assert first.status == PaymentStatus.PENDING and first.expires_at is not None
    assert await balance(payments.users[0].id) == 5
    if provider == "crypto":
        assert len(payments.requests) == 1
        request = payments.requests[0]
        data = json.loads(request.content)
        assert request.headers["ApiSecret"] == SECRET
        assert str(request.url) == "https://api.atlos.io/gateway/rest/Invoice/Create"
        assert data["OrderId"] == str(first.id)
        assert data["OrderAmount"] == 10 and data["SendEmail"] is False
        assert first.provider_invoice_id == "invoice-1"
    else:
        payments.bot.create_invoice_link.assert_awaited_once()
        data = payments.bot.create_invoice_link.call_args.kwargs
        assert data["payload"] == str(first.id) and data["currency"] == "XTR"
        assert data["provider_token"] == ""
        assert len(data["prices"]) == 1 and data["prices"][0].amount == 50
        assert first.telegram_user_id == 123


async def test_crypto_invoice_sends_public_postback_url(payments):
    async with db_session.session_scope() as session:
        await payments.crypto(
            session,
            postback_url="https://unkre.cc/api/payments/webhooks/atlos",
        ).create_invoice(
            payments.users[0].id,
            credits=20,
            amount=Decimal(10),
            idempotency_key=str(uuid7()),
        )
    data = json.loads(payments.requests[-1].content)
    assert data["PostbackUrl"] == "https://unkre.cc/api/payments/webhooks/atlos"


async def test_crypto_request_preserves_decimal_precision(payments):
    amount = Decimal("12.123456789123456789")
    await invoice(payments, amount=amount)
    data = json.loads(payments.requests[0].content, parse_float=Decimal)
    assert data["OrderAmount"] == amount


@pytest.mark.parametrize("provider", ["crypto", "stars"])
@pytest.mark.parametrize("changes", [{"credits": 21}, {"user": 1}])
async def test_idempotency_key_cannot_change_order_or_owner(
    payments, provider, changes
):
    await invoice(payments, provider, idempotency_key="same")
    with pytest.raises(InvalidPaymentStateError):
        await invoice(payments, provider, idempotency_key="same", **changes)


async def test_idempotency_key_cannot_switch_provider(payments):
    await invoice(payments, "crypto", idempotency_key="same")
    with pytest.raises(InvalidPaymentStateError):
        await invoice(payments, "stars", idempotency_key="same")
    payments.bot.create_invoice_link.assert_not_awaited()


@pytest.mark.parametrize("provider", ["crypto", "stars"])
async def test_blocked_user_cannot_create_invoice(payments, provider):
    with pytest.raises(UserBlockedError):
        await invoice(payments, provider, user=3)
    assert not payments.requests
    payments.bot.create_invoice_link.assert_not_awaited()


async def test_stars_allows_google_account_without_telegram_link(payments):
    payment = await invoice(payments, "stars", user=2)
    assert payment.telegram_user_id is None
    assert payment.currency == "XTR"
    payments.bot.create_invoice_link.assert_awaited_once()


@pytest.mark.parametrize("amount", [1.2, True, Decimal("NaN"), Decimal(-1)])
async def test_crypto_rejects_invalid_money_before_provider(payments, amount):
    with pytest.raises(ValidationError):
        await invoice(payments, amount=amount)
    assert not payments.requests


@pytest.mark.parametrize("stars", [0, -1, True, 1.5])
async def test_stars_requires_positive_integer_price(payments, stars):
    with pytest.raises(ValidationError):
        await invoice(payments, "stars", stars=stars)
    payments.bot.create_invoice_link.assert_not_awaited()


@pytest.mark.parametrize("provider", ["crypto", "stars"])
async def test_user_can_only_read_own_provider_payments(payments, provider):
    first = await invoice(payments, provider)
    await invoice(payments, provider, user=1)
    other = await invoice(payments, "stars" if provider == "crypto" else "crypto")
    async with db_session.session_scope() as session:
        service = getattr(payments, provider)(session)
        assert (
            await service.get_payment(payments.users[0].id, first.id)
        ).id == first.id
        assert [
            item.id for item in await service.get_payments(payments.users[0].id)
        ] == [first.id]
        with pytest.raises(InvalidPaymentStateError):
            await service.get_payment(payments.users[1].id, first.id)
        with pytest.raises(InvalidPaymentStateError):
            await service.get_payment(payments.users[0].id, other.id)


@pytest.mark.parametrize("provider", ["crypto", "stars"])
async def test_confirmed_payment_credits_once_and_records_balances(payments, provider):
    payment = await invoice(payments, provider)
    for expected in (True, False):
        async with db_session.session_scope() as session:
            service = getattr(payments, provider)(session)
            if provider == "crypto":
                assert (
                    await service.handle_postback(*signed(transaction(payment)))
                    is expected
                )
            else:
                assert (
                    await service.handle_successful_payment(message(payment))
                    is expected
                )
    assert await balance(payments.users[0].id) == 25
    async with db_session.session_scope() as session:
        saved = await session.get(PaymentModel, payment.id)
        ledger = (await session.scalars(select(TransactionModel))).one()
        assert saved.status == PaymentStatus.SUCCEEDED and saved.paid_at is not None
        assert (
            ledger.type == TransactionType.PURCHASE and ledger.payment_id == payment.id
        )
        assert (ledger.balance_before, ledger.amount, ledger.balance_after) == (
            5,
            20,
            25,
        )
        if provider == "crypto":
            assert saved.asset_code == "USDC" and saved.blockchain_code == "ETH"
            assert (
                saved.blockchain_hash.startswith("hash-")
                and saved.sender_address == "sender"
            )


async def test_invalid_crypto_signature_and_modified_body_never_credit(payments):
    payment = await invoice(payments)
    body, signature = signed(transaction(payment))
    for raw, sig in [(body, "bad"), (body + b" ", signature)]:
        async with db_session.session_scope() as session:
            with pytest.raises(InvalidPaymentStateError):
                await payments.crypto(session).handle_postback(raw, sig)
    assert await balance(payments.users[0].id) == 5


@pytest.mark.parametrize(
    "changes",
    [
        {"MerchantId": "other"},
        {"OrderAmount": 1},
        {"OrderCurrency": "EUR"},
        {"PaidAmount": 9},
        {"TimeSent": "2026-10-30T12:00:00"},
        {"Fee": 20},
        {"Asset": None},
    ],
)
async def test_crypto_rejects_mismatched_or_invalid_confirmation(payments, changes):
    payment = await invoice(payments)
    with pytest.raises((InvalidPaymentStateError, ValidationError)):
        async with db_session.session_scope() as session:
            await payments.crypto(session).handle_postback(
                *signed(transaction(payment, **changes))
            )
    assert await balance(payments.users[0].id) == 5


async def test_unconfirmed_crypto_transaction_does_not_credit(payments):
    payment = await invoice(payments)
    async with db_session.session_scope() as session:
        assert (
            await payments.crypto(session).handle_postback(
                *signed(transaction(payment, Status=0))
            )
            is False
        )
    assert await balance(payments.users[0].id) == 5


async def test_stars_pre_checkout_reserves_order_without_credit(payments):
    payment = await invoice(payments, "stars")
    async with db_session.session_scope() as session:
        checked = await payments.stars(session).validate_pre_checkout(checkout(payment))
        assert checked.status == PaymentStatus.PROCESSING
    assert await balance(payments.users[0].id) == 5
    async with db_session.session_scope() as session:
        with pytest.raises(InvalidPaymentStateError):
            await payments.stars(session).validate_pre_checkout(checkout(payment))
        assert await payments.stars(session).handle_successful_payment(message(payment))
    assert await balance(payments.users[0].id) == 25


async def test_google_user_can_pay_stars_from_any_telegram_account(payments):
    payment = await invoice(payments, "stars", user=2)
    assert payment.telegram_user_id is None
    async with db_session.session_scope() as session:
        checked = await payments.stars(session).validate_pre_checkout(
            checkout(payment, user=999)
        )
        assert checked.status == PaymentStatus.PROCESSING
    async with db_session.session_scope() as session:
        assert await payments.stars(session).handle_successful_payment(
            message(payment, user=999)
        )
    assert await balance(payments.users[2].id) == 25


@pytest.mark.parametrize(
    "changes",
    [
        {"user": 456},
        {"currency": "USD"},
        {"total_amount": 1},
        {"invoice_payload": "bad"},
    ],
)
async def test_stars_rejects_mismatched_payer_amount_currency_and_payload(
    payments, changes
):
    payment = await invoice(payments, "stars")
    async with db_session.session_scope() as session:
        with pytest.raises(InvalidPaymentStateError):
            await payments.stars(session).handle_successful_payment(
                message(payment, **changes)
            )
    assert await balance(payments.users[0].id) == 5


@pytest.mark.parametrize("provider", ["crypto", "stars"])
async def test_late_confirmed_payment_is_credited_after_expiration(payments, provider):
    payment = await invoice(payments, provider)
    async with db_session.session_scope() as session:
        saved = await session.get(PaymentModel, payment.id)
        saved.status = PaymentStatus.EXPIRED
        saved.expires_at = datetime.now(UTC) - timedelta(hours=1)
    async with db_session.session_scope() as session:
        service = getattr(payments, provider)(session)
        if provider == "crypto":
            assert await service.handle_postback(*signed(transaction(payment)))
        else:
            assert await service.handle_successful_payment(message(payment))
    assert await balance(payments.users[0].id) == 25


async def test_same_charge_cannot_pay_two_invoices_and_failure_preserves_balance(
    payments,
):
    first = await invoice(payments, "stars")
    second = await invoice(payments, "stars")
    async with db_session.session_scope() as session:
        await payments.stars(session).handle_successful_payment(
            message(first, telegram_payment_charge_id="same-charge")
        )
    async with db_session.session_scope() as session:
        with pytest.raises(InvalidPaymentStateError):
            await payments.stars(session).handle_successful_payment(
                message(second, telegram_payment_charge_id="same-charge")
            )
    assert await balance(payments.users[0].id) == 25
    async with db_session.session_scope() as session:
        assert (
            await session.get(PaymentModel, second.id)
        ).status == PaymentStatus.PENDING
        assert (
            await session.scalar(select(func.count()).select_from(TransactionModel))
            == 1
        )


async def test_invoice_and_settlement_never_commit_the_outer_transaction(payments):
    with pytest.raises(RuntimeError):
        async with db_session.session_scope() as session:
            await payments.stars(session).create_invoice(
                payments.users[0].id,
                stars=50,
                credits=20,
                idempotency_key="rolled-back",
            )
            raise RuntimeError("cancel transaction")
    async with db_session.session_scope() as session:
        assert await session.scalar(select(func.count()).select_from(PaymentModel)) == 0
    payment = await invoice(payments, "stars")
    with pytest.raises(RuntimeError):
        async with db_session.session_scope() as session:
            await payments.stars(session).handle_successful_payment(message(payment))
            raise RuntimeError("cancel settlement")
    assert await balance(payments.users[0].id) == 5
    async with db_session.session_scope() as session:
        assert (
            await session.get(PaymentModel, payment.id)
        ).status == PaymentStatus.PENDING
        assert (
            await session.scalar(select(func.count()).select_from(TransactionModel))
            == 0
        )


async def test_crypto_reconciliation_paginates_and_shares_idempotency_with_postback(
    payments,
):
    first = await invoice(payments)
    second = await invoice(payments, user=1)
    data = transaction(first)
    data["AssetCode"] = data.pop("Asset")
    data["BlockchainCode"] = data.pop("Blockchain")
    data["SenderAddress"] = data.pop("UserWallet")
    data["Id"] = data.pop("TransactionId")
    payments.transactions = [
        data,
        transaction(second),
        transaction(first, OrderId=str(uuid7())),
    ]
    async with db_session.session_scope() as session:
        assert (
            await payments.crypto(session).reconcile(
                since=datetime.now(UTC) - timedelta(days=1), page_size=1
            )
            == 2
        )
    async with db_session.session_scope() as session:
        assert (
            await payments.crypto(session).handle_postback(*signed(transaction(first)))
            is False
        )
    assert await balance(payments.users[0].id) == 25
    assert await balance(payments.users[1].id) == 25
    requests = [
        json.loads(item.content)
        for item in payments.requests
        if item.url.path.endswith("Transaction/List")
    ]
    assert [item["Skip"] for item in requests] == [0, 1, 2]
    assert len({item["TimeFinish"] for item in requests}) == 1
    for item in requests:
        for key in ("TimeStart", "TimeFinish"):
            parsed = datetime.fromisoformat(item[key])
            assert parsed.utcoffset() == timedelta(0)


async def test_stars_reconciliation_ignores_outgoing_and_unrelated_transactions(
    payments,
):
    payment = await invoice(payments, "stars")
    source = TransactionPartnerUser(
        transaction_type="invoice_payment",
        user=User(id=123, is_bot=False, first_name="Test"),
        invoice_payload=str(payment.id),
    )
    now = datetime.now(UTC)
    payments.bot.get_star_transactions.side_effect = [
        StarTransactions(
            transactions=[
                StarTransaction(
                    id="charge-" + str(payment.id), amount=50, date=now, source=source
                )
            ]
        ),
        StarTransactions(
            transactions=[
                StarTransaction(id="refund", amount=50, date=now, receiver=source)
            ]
        ),
        StarTransactions(transactions=[]),
    ]
    async with db_session.session_scope() as session:
        assert (
            await payments.stars(session).reconcile(
                since=now - timedelta(days=1), page_size=1
            )
            == 1
        )
    async with db_session.session_scope() as session:
        assert (
            await payments.stars(session).handle_successful_payment(message(payment))
            is False
        )
    assert await balance(payments.users[0].id) == 25
    assert [
        call.kwargs["offset"]
        for call in payments.bot.get_star_transactions.call_args_list
    ] == [0, 1, 2]


async def test_crypto_provider_failure_rolls_back_invoice(payments):
    payments.response = httpx.Response(503)
    with pytest.raises(PaymentProviderError):
        await invoice(payments)
    async with db_session.session_scope() as session:
        assert await session.scalar(select(func.count()).select_from(PaymentModel)) == 0
    assert await balance(payments.users[0].id) == 5


@pytest.mark.parametrize("provider", ["crypto", "stars"])
async def test_reconciliation_isolates_invalid_payment_and_continues(
    payments, provider
):
    orders = [await invoice(payments, provider) for _ in range(3)]
    now = datetime.now(UTC)
    if provider == "crypto":
        payments.transactions = [
            transaction(order, PaidAmount=9 if index == 1 else 10)
            for index, order in enumerate(orders)
        ]
    else:
        payments.bot.get_star_transactions.return_value = StarTransactions(
            transactions=[
                StarTransaction(
                    id=f"charge-{order.id}",
                    amount=49 if index == 1 else 50,
                    date=now,
                    source=TransactionPartnerUser(
                        transaction_type="invoice_payment",
                        user=User(id=123, is_bot=False, first_name="Test"),
                        invoice_payload=str(order.id),
                    ),
                )
                for index, order in enumerate(orders)
            ]
        )
    async with db_session.session_scope() as session:
        assert (
            await getattr(payments, provider)(session).reconcile(
                since=now - timedelta(days=1)
            )
            == 2
        )
    assert await balance(payments.users[0].id) == 45
    async with db_session.session_scope() as session:
        assert (
            await session.get(PaymentModel, orders[1].id)
        ).status == PaymentStatus.PENDING
        assert (
            await session.scalar(select(func.count()).select_from(TransactionModel))
            == 2
        )


@pytest.mark.parametrize("provider", ["crypto", "stars"])
async def test_reconciliation_rolls_back_purchase_if_referral_fails(payments, provider):
    from domain.exceptions.referral import InvalidReferralError

    first = await invoice(payments, provider)
    second = await invoice(payments, provider, user=1)
    now = datetime.now(UTC)
    if provider == "crypto":
        payments.transactions = [transaction(first), transaction(second)]
    else:
        payments.bot.get_star_transactions.return_value = StarTransactions(
            transactions=[
                StarTransaction(
                    id=f"charge-{order.id}",
                    amount=50,
                    date=now,
                    source=TransactionPartnerUser(
                        transaction_type="invoice_payment",
                        user=User(id=payer, is_bot=False, first_name="Test"),
                        invoice_payload=str(order.id),
                    ),
                )
                for order, payer in [(first, 123), (second, 456)]
            ]
        )
    async with db_session.session_scope() as session:
        service = getattr(payments, provider)(session)
        service._referrals = SimpleNamespace(
            reward_for_purchase=AsyncMock(
                side_effect=[InvalidReferralError("failure"), True]
            )
        )
        assert await service.reconcile(since=now - timedelta(days=1)) == 1
    assert await balance(payments.users[0].id) == 5
    assert await balance(payments.users[1].id) == 25
    async with db_session.session_scope() as session:
        assert (
            await session.get(PaymentModel, first.id)
        ).status == PaymentStatus.PENDING
        assert (
            await session.scalar(select(func.count()).select_from(TransactionModel))
            == 1
        )


@pytest.mark.parametrize("reconcile", [False, True])
async def test_unlinked_stars_payer_is_recorded_and_cannot_be_replaced(
    payments, reconcile
):
    payment = await invoice(payments, "stars", user=2, idempotency_key="unlinked")
    now = datetime.now(UTC)
    async with db_session.session_scope() as session:
        service = payments.stars(session)
        if reconcile:
            payments.bot.get_star_transactions.return_value = StarTransactions(
                transactions=[
                    StarTransaction(
                        id=f"charge-{payment.id}",
                        amount=50,
                        date=now,
                        source=TransactionPartnerUser(
                            transaction_type="invoice_payment",
                            user=User(id=999, is_bot=False, first_name="Payer"),
                            invoice_payload=str(payment.id),
                        ),
                    )
                ]
            )
            assert await service.reconcile(since=now - timedelta(days=1)) == 1
        else:
            assert await service.handle_successful_payment(message(payment, user=999))
    async with db_session.session_scope() as session:
        saved = await session.get(PaymentModel, payment.id)
        assert saved.telegram_user_id == 999
        assert not await payments.stars(session).handle_successful_payment(
            message(payment, user=999)
        )
        with pytest.raises(InvalidPaymentStateError):
            await payments.stars(session).handle_successful_payment(
                message(payment, user=888)
            )
    replay = await invoice(payments, "stars", user=2, idempotency_key="unlinked")
    assert replay.id == payment.id and replay.telegram_user_id == 999
    assert await balance(payments.users[2].id) == 25


@pytest.mark.parametrize("stage", ["pre_checkout", "settlement"])
async def test_polling_handler_rolls_back_on_failure(payments, monkeypatch, stage):
    from adapters.bot import payments as bot_payments

    payment = await invoice(payments, "stars")
    reply = AsyncMock()

    async def failing_service(session, bot, settings):
        service = payments.stars(session)
        if stage == "pre_checkout":
            validate = service.validate_pre_checkout

            async def fail_after_reservation(query):
                await validate(query)
                raise RuntimeError("failure after reservation")

            service.validate_pre_checkout = fail_after_reservation
        else:
            service._referrals = SimpleNamespace(
                reward_for_purchase=AsyncMock(
                    side_effect=RuntimeError("referral failed")
                )
            )
        return service

    monkeypatch.setattr(bot_payments, "stars_service", failing_service)
    router = bot_payments.build_payment_router(bot=payments.bot, settings=None)
    if stage == "pre_checkout":
        monkeypatch.setattr(PreCheckoutQuery, "answer", reply)
        await router.pre_checkout_query.handlers[0].callback(checkout(payment))
        assert reply.call_args.kwargs["ok"] is False
    else:
        monkeypatch.setattr(Message, "answer", reply)
        await router.message.handlers[0].callback(message(payment))
        reply.assert_not_awaited()
    assert await balance(payments.users[0].id) == 5
    async with db_session.session_scope() as session:
        assert (
            await session.get(PaymentModel, payment.id)
        ).status == PaymentStatus.PENDING
        assert (
            await session.scalar(select(func.count()).select_from(TransactionModel))
            == 0
        )


async def test_polling_handler_does_not_acknowledge_failed_commit(
    payments, monkeypatch
):
    from contextlib import asynccontextmanager

    from adapters.bot import payments as bot_payments

    payment = await invoice(payments, "stars")
    reply = AsyncMock()

    @asynccontextmanager
    async def failed_commit():
        async with db_session.session_scope() as session:
            yield session
            raise RuntimeError("commit failed")

    async def service(session, bot, settings):
        return payments.stars(session)

    monkeypatch.setattr(bot_payments, "session_scope", failed_commit)
    monkeypatch.setattr(bot_payments, "stars_service", service)
    monkeypatch.setattr(Message, "answer", reply)
    router = bot_payments.build_payment_router(bot=payments.bot, settings=None)
    await router.message.handlers[0].callback(message(payment))
    reply.assert_not_awaited()
    assert await balance(payments.users[0].id) == 5
