import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import String, create_engine, event, insert, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.schema import CreateTable

from adapters.database.models import (
    Base,
    PaymentModel,
    PaymentRefundModel,
    TransactionModel,
    UserModel,
    WalletModel,
)
from domain.enums import (
    PaymentProvider,
    PaymentRefundStatus,
    PaymentStatus,
    TransactionType,
)
from domain.exceptions.payments import (
    ImmutableTransactionError,
    InvalidPaymentAmountError,
    InvalidPaymentStateError,
)
from domain.validators import PaymentAmountValidator


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'payments.db'}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def wallet(session):
    wallet = WalletModel(user=UserModel(first_name="Test"))
    session.add(wallet)
    session.commit()
    return wallet


def payment(wallet, **overrides):
    values = dict(
        wallet=wallet,
        provider=PaymentProvider.TELEGRAM_STARS,
        credits=500,
        amount=Decimal("100"),
        currency="XTR",
        telegram_user_id=123,
        idempotency_key=str(uuid.uuid7()),
    )
    values.update(overrides)
    if (
        values.get("status") == PaymentStatus.SUCCEEDED
        and "paid_amount" not in overrides
    ):
        values["paid_amount"] = values["amount"]
    return PaymentModel(**values)


def complete_payment(session, wallet):
    item = payment(
        wallet,
        status=PaymentStatus.SUCCEEDED,
        paid_at=datetime.now(UTC),
        provider_transaction_id=str(uuid.uuid7()),
    )
    session.add(item)
    session.commit()
    return item


def transaction(wallet, **overrides):
    values = dict(
        wallet=wallet,
        type=TransactionType.ADJUSTMENT,
        amount=10,
        balance_before=0,
        balance_after=10,
        idempotency_key=str(uuid.uuid7()),
    )
    values.update(overrides)
    return TransactionModel(**values)


def test_wallet_is_the_only_user_balance(session, wallet):
    assert "credits" not in UserModel.__table__.c
    assert wallet.credits == 0
    wallet.credits = 100
    session.commit()
    assert wallet.user.credits == 100
    assert wallet.user.wallet is wallet


def test_one_wallet_per_user(session, wallet):
    session.add(WalletModel(user_id=wallet.user_id))
    with pytest.raises(IntegrityError):
        session.commit()


def test_stars_payment_allows_an_unlinked_payer(session, wallet):
    item = payment(wallet, telegram_user_id=None)
    session.add(item)
    session.commit()
    assert item.telegram_user_id is None
    assert item.provider == PaymentProvider.TELEGRAM_STARS


def test_atlos_payment_details(session, wallet):
    item = payment(
        wallet,
        provider=PaymentProvider.ATLOS,
        currency="USD",
        amount=Decimal("20.25"),
        telegram_user_id=None,
        status=PaymentStatus.SUCCEEDED,
        paid_at=datetime.now(UTC),
        provider_invoice_id="invoice-1",
        provider_payment_id="payment-1",
        provider_transaction_id="transaction-1",
        asset_code="USDC",
        blockchain_code="ETH",
        asset_amount=Decimal("20.25"),
        asset_fee=Decimal("0.25"),
        blockchain_hash="0xabc",
        sender_address="0xsender",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    assert item.provider == PaymentProvider.ATLOS
    assert item.amount == Decimal("20.25")
    assert item.asset_fee == Decimal("0.25")
    assert wallet.user.payments == [item]


def test_purchase_and_refund_have_separate_credit_movements(session, wallet):
    item = complete_payment(session, wallet)
    purchase = transaction(
        wallet,
        type=TransactionType.PURCHASE,
        payment=item,
        amount=500,
        balance_after=500,
    )
    wallet.credits = 500
    session.add(purchase)
    session.commit()
    refund = PaymentRefundModel(
        payment=item, idempotency_key="refund-1", reason="Customer request"
    )
    debit = transaction(
        wallet,
        type=TransactionType.REFUND,
        payment_refund=refund,
        amount=-500,
        balance_before=500,
        balance_after=0,
    )
    wallet.credits = 0
    session.add(debit)
    session.commit()
    assert item.transaction is purchase
    assert item.refund is refund
    assert refund.transaction is debit
    assert refund.amount == item.amount
    assert refund.credits == 500
    assert refund.currency == "XTR"
    assert refund.wallet_id == wallet.id
    assert wallet.credits == 0


def test_duplicate_charge_is_rejected(session, wallet):
    original = complete_payment(session, wallet)
    session.add(
        payment(wallet, provider_transaction_id=original.provider_transaction_id)
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_only_one_purchase_per_payment_and_rollback_is_atomic(session, wallet):
    item = complete_payment(session, wallet)
    session.add(
        transaction(
            wallet,
            type=TransactionType.PURCHASE,
            payment=item,
            amount=500,
            balance_after=500,
        )
    )
    wallet.credits = 500
    session.commit()
    session.add(
        transaction(
            wallet,
            payment_id=item.id,
            type=TransactionType.PURCHASE,
            amount=500,
            balance_before=500,
            balance_after=1000,
        )
    )
    wallet.credits = 1000
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    assert session.get(WalletModel, wallet.id).credits == 500


def test_one_full_refund_per_payment(session, wallet):
    item = complete_payment(session, wallet)
    session.add(
        PaymentRefundModel(payment=item, idempotency_key="first", reason="Request")
    )
    session.commit()
    session.add(
        PaymentRefundModel(
            payment_id=item.id,
            wallet_id=wallet.id,
            idempotency_key="second",
            reason="Duplicate",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_idempotency_keys_are_unique(session, wallet):
    session.add_all(
        [
            payment(wallet, idempotency_key="same"),
            payment(wallet, idempotency_key="same"),
        ]
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_wallet_version_rejects_lost_update(engine, wallet):
    with Session(engine) as first, Session(engine) as second:
        a = first.get(WalletModel, wallet.id)
        b = second.get(WalletModel, wallet.id)
        a.credits = 10
        first.commit()
        b.credits = 20
        with pytest.raises(StaleDataError):
            second.commit()


@pytest.mark.parametrize("delete", [False, True])
def test_posted_transaction_cannot_be_rewritten(session, wallet, delete):
    row = transaction(wallet)
    session.add(row)
    session.commit()
    if delete:
        session.delete(row)
    else:
        row.description = "Changed"
    with pytest.raises(ImmutableTransactionError):
        session.flush()


def test_spend_can_be_reversed_once(session, wallet):
    spend = transaction(
        wallet,
        type=TransactionType.SPEND,
        amount=-10,
        balance_before=10,
        balance_after=0,
    )
    session.add(spend)
    session.commit()
    session.add(
        transaction(wallet, type=TransactionType.REVERSAL, reverses_transaction=spend)
    )
    session.commit()
    session.add(
        transaction(
            wallet, type=TransactionType.REVERSAL, reverses_transaction_id=spend.id
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_transaction_cannot_reference_another_wallet_payment(session, wallet):
    item = complete_payment(session, wallet)
    other = WalletModel(user=UserModel(first_name="Other"))
    session.add(other)
    session.commit()
    with pytest.raises(IntegrityError):
        session.execute(
            insert(TransactionModel.__table__).values(
                id=uuid.uuid7(),
                wallet_id=other.id,
                type=TransactionType.PURCHASE,
                payment_id=item.id,
                amount=500,
                balance_before=0,
                balance_after=500,
                idempotency_key="wrong-owner",
            )
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"credits": 0},
        {"amount": Decimal("0")},
        {"amount": Decimal("1.5")},
        {"currency": "USD"},
        {"currency": "xtr"},
        {"currency": "123"},
        {"currency": "X1R"},
        {"telegram_user_id": 0},
        {"provider": "unknown"},
        {"status": "unknown"},
        {"idempotency_key": ""},
        {"provider_invoice_id": "x" * 256},
        {"provider_transaction_id": ""},
        {"asset_code": "USDC"},
        {"status": PaymentStatus.SUCCEEDED},
    ],
)
def test_database_payment_checks(session, wallet, changes):
    item = payment(wallet)
    session.add(item)
    session.commit()
    with pytest.raises(IntegrityError):
        session.execute(
            update(PaymentModel.__table__)
            .where(PaymentModel.id == item.id)
            .values(**changes)
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": 0},
        {"balance_after": -1},
        {"balance_before": -1},
        {"balance_after": 11},
        {"type": TransactionType.PURCHASE},
        {"type": TransactionType.SPEND},
        {"idempotency_key": ""},
    ],
)
def test_database_transaction_checks(session, wallet, changes):
    row = transaction(wallet)
    session.add(row)
    session.commit()
    with pytest.raises(IntegrityError):
        session.execute(
            update(TransactionModel.__table__)
            .where(TransactionModel.id == row.id)
            .values(**changes)
        )


def test_wallet_cannot_be_negative_in_sql(session, wallet):
    with pytest.raises(IntegrityError):
        session.execute(update(WalletModel.__table__).values(credits=-1))


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        True,
        1.5,
        "1.5",
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("0.0000000000000000001"),
        Decimal("100000000000000000000"),
    ],
)
def test_invalid_monetary_amounts(value):
    with pytest.raises(InvalidPaymentAmountError):
        PaymentAmountValidator.validate(value)


def test_decimal_precision_and_optional_amounts():
    value = Decimal("99999999999999999999.999999999999999999")
    assert PaymentAmountValidator.validate(value) == value
    assert PaymentAmountValidator.validate(Decimal("0.000000000000000001")) == Decimal(
        "1e-18"
    )
    assert PaymentAmountValidator.validate(Decimal("1.0000000000000000000")) == Decimal(
        "1"
    )
    assert PaymentAmountValidator.validate(0, allow_zero=True) == Decimal("0")
    assert PaymentAmountValidator.validate(None, nullable=True) is None


def test_payment_ddl_and_bounded_strings():
    dialect = postgresql.dialect()
    for model in (WalletModel, PaymentModel, PaymentRefundModel, TransactionModel):
        ddl = str(CreateTable(model.__table__).compile(dialect=dialect))
        assert "CHECK" in ddl
        for column in model.__table__.columns:
            if isinstance(column.type, String):
                assert column.type.length is not None
    assert "NUMERIC(38, 18)" in str(
        CreateTable(PaymentModel.__table__).compile(dialect=dialect)
    )


def test_pending_payment_cannot_credit_wallet(session, wallet):
    item = payment(wallet)
    session.add(
        transaction(
            wallet,
            payment=item,
            type=TransactionType.PURCHASE,
            amount=500,
            balance_after=500,
        )
    )
    with pytest.raises(InvalidPaymentStateError):
        session.flush()


def test_purchase_amount_must_match_payment(session, wallet):
    item = complete_payment(session, wallet)
    session.add(transaction(wallet, payment=item, type=TransactionType.PURCHASE))
    with pytest.raises(InvalidPaymentStateError):
        session.flush()


def test_pending_payment_cannot_be_refunded(session, wallet):
    item = payment(wallet)
    session.add(
        PaymentRefundModel(
            payment=item, reason="Request", idempotency_key="pending-refund"
        )
    )
    with pytest.raises(InvalidPaymentStateError):
        session.flush()


def test_refund_debit_must_match_full_purchase(session, wallet):
    item = complete_payment(session, wallet)
    refund = PaymentRefundModel(
        payment=item, reason="Request", idempotency_key="refund"
    )
    session.add(
        transaction(
            wallet,
            payment_refund=refund,
            type=TransactionType.REFUND,
            amount=-10,
            balance_before=10,
            balance_after=0,
        )
    )
    with pytest.raises(InvalidPaymentStateError):
        session.flush()


def test_reversal_cannot_increase_original_spend(session, wallet):
    original = transaction(
        wallet,
        type=TransactionType.SPEND,
        amount=-10,
        balance_before=10,
        balance_after=0,
    )
    session.add(original)
    session.commit()
    session.add(
        transaction(
            wallet,
            type=TransactionType.REVERSAL,
            reverses_transaction=original,
            amount=20,
            balance_after=20,
        )
    )
    with pytest.raises(InvalidPaymentStateError):
        session.flush()


@pytest.mark.parametrize(
    "field,value",
    [
        ("credits", 1000),
        ("amount", Decimal("200")),
        ("currency", "USD"),
        ("idempotency_key", "changed"),
        ("telegram_user_id", 999),
    ],
)
def test_payment_purchase_snapshot_cannot_change(session, wallet, field, value):
    item = payment(wallet)
    session.add(item)
    session.commit()
    setattr(item, field, value)
    with pytest.raises(InvalidPaymentStateError):
        session.flush()


def test_atlos_refund_tracks_outgoing_payment(session, wallet):
    item = payment(
        wallet,
        provider=PaymentProvider.ATLOS,
        telegram_user_id=None,
        currency="USD",
        amount=Decimal("20.25"),
        provider_transaction_id="original-transaction",
        status=PaymentStatus.SUCCEEDED,
        paid_at=datetime.now(UTC),
        asset_code="USDC",
        blockchain_code="ETH",
        asset_amount=Decimal("20.25"),
    )
    session.add(item)
    session.commit()
    refund = PaymentRefundModel(
        payment=item,
        reason="Request",
        idempotency_key="atlos-refund",
        status=PaymentRefundStatus.SUCCEEDED,
        completed_at=datetime.now(UTC),
        atlos_payout_invoice_id="outgoing-invoice",
        recipient_address="0xrecipient",
        blockchain_hash="0xrefund",
        asset_amount=Decimal("20.25"),
    )
    session.add(refund)
    session.commit()
    assert refund.amount == Decimal("20.25")
    assert refund.payment.asset_code == "USDC"
    assert refund.atlos_payout_invoice_id == "outgoing-invoice"


def test_atlos_successful_refund_requires_payout_details(session, wallet):
    item = payment(
        wallet,
        provider=PaymentProvider.ATLOS,
        telegram_user_id=None,
        currency="USD",
        provider_transaction_id="original-transaction",
        status=PaymentStatus.SUCCEEDED,
        paid_at=datetime.now(UTC),
    )
    session.add(item)
    session.commit()
    session.add(
        PaymentRefundModel(
            payment=item,
            reason="Request",
            idempotency_key="missing-payout",
            status=PaymentRefundStatus.SUCCEEDED,
            completed_at=datetime.now(UTC),
        )
    )
    with pytest.raises(InvalidPaymentStateError):
        session.flush()


def test_stars_refund_cannot_have_crypto_payout(session, wallet):
    item = complete_payment(session, wallet)
    session.add(
        PaymentRefundModel(
            payment=item,
            reason="Request",
            idempotency_key="wrong-provider",
            recipient_address="0xrecipient",
        )
    )
    with pytest.raises(InvalidPaymentStateError):
        session.flush()


def test_refund_wallet_is_checked_by_database(session, wallet):
    item = complete_payment(session, wallet)
    other = WalletModel(user=UserModel(first_name="Other"))
    session.add(other)
    session.commit()
    with pytest.raises(IntegrityError):
        session.execute(
            insert(PaymentRefundModel.__table__).values(
                id=uuid.uuid7(),
                payment_id=item.id,
                wallet_id=other.id,
                status=PaymentRefundStatus.PENDING,
                idempotency_key="wrong-owner",
                reason="Request",
            )
        )


def test_positive_adjustment_and_spend_balance_records(session, wallet):
    topup = transaction(wallet)
    wallet.credits = 10
    session.add(topup)
    session.commit()
    spend = transaction(
        wallet,
        type=TransactionType.SPEND,
        amount=-4,
        balance_before=10,
        balance_after=6,
    )
    wallet.credits = 6
    session.add(spend)
    session.commit()
    assert wallet.user.credits == 6
    assert wallet.transactions == [topup, spend]


def test_unchanged_payment_relationship_does_not_rewrite_ledger(session, wallet):
    item = complete_payment(session, wallet)
    row = transaction(
        wallet,
        payment=item,
        type=TransactionType.PURCHASE,
        amount=500,
        balance_after=500,
    )
    session.add(row)
    session.commit()
    item.transaction = row
    session.commit()


def test_success_cannot_hide_underpayment(session, wallet):
    item = payment(
        wallet,
        provider=PaymentProvider.ATLOS,
        telegram_user_id=None,
        currency="USD",
        amount=Decimal("20"),
        paid_amount=Decimal("19"),
        status=PaymentStatus.SUCCEEDED,
        paid_at=datetime.now(UTC),
        provider_transaction_id="underpaid",
    )
    session.add(item)
    with pytest.raises(IntegrityError):
        session.flush()


def test_stars_requires_exact_received_amount(session, wallet):
    item = payment(
        wallet,
        paid_amount=Decimal("101"),
        status=PaymentStatus.SUCCEEDED,
        paid_at=datetime.now(UTC),
        provider_transaction_id="wrong-total",
    )
    session.add(item)
    with pytest.raises(IntegrityError):
        session.flush()


def test_refund_remembers_overpaid_crypto_order(session, wallet):
    item = payment(
        wallet,
        provider=PaymentProvider.ATLOS,
        telegram_user_id=None,
        currency="USD",
        amount=Decimal("20"),
        paid_amount=Decimal("21"),
        status=PaymentStatus.SUCCEEDED,
        paid_at=datetime.now(UTC),
        provider_transaction_id="overpaid",
    )
    refund = PaymentRefundModel(
        payment=item, reason="Request", idempotency_key="overpaid-refund"
    )
    session.add(refund)
    session.commit()
    assert refund.amount == Decimal("21")
    assert refund.payment.amount == Decimal("20")
