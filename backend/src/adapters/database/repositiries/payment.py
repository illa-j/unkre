from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from adapters.database.models import (
    PaymentModel,
    PaymentRefundModel,
    TransactionModel,
    WalletModel,
)
from adapters.database.repositiries import CrudRepository
from domain.entities.payment import Payment
from domain.enums import PaymentProvider, PaymentStatus
from domain.exceptions.payments import InvalidPaymentStateError, PaymentNotFoundError
from ports import DatabaseManagerInterface


class PaymentRepository(CrudRepository[PaymentModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, PaymentModel)

    @asynccontextmanager
    async def settlement_scope(self) -> AsyncIterator[None]:
        async with self._db.db.begin_nested():
            yield

    async def get_for_user(
        self, user_id: UUID, payment_id: UUID, provider: PaymentProvider
    ) -> Payment | None:
        row = await self._db.scalar(
            select(PaymentModel)
            .join(WalletModel, PaymentModel.wallet_id == WalletModel.id)
            .where(
                PaymentModel.id == payment_id,
                PaymentModel.provider == provider,
                WalletModel.user_id == user_id,
            )
        )
        return row.to_entity() if row is not None else None

    async def list_for_user(
        self, user_id: UUID, provider: PaymentProvider, *, limit: int, offset: int
    ) -> list[Payment]:
        rows = await self._db.scalars(
            select(PaymentModel)
            .join(WalletModel, PaymentModel.wallet_id == WalletModel.id)
            .where(WalletModel.user_id == user_id, PaymentModel.provider == provider)
            .order_by(PaymentModel.created_at.desc(), PaymentModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [row.to_entity() for row in rows]

    async def get_for_update(
        self, payment_id: UUID, provider: PaymentProvider
    ) -> Payment | None:
        row = await self._db.scalar(
            select(PaymentModel)
            .where(PaymentModel.id == payment_id, PaymentModel.provider == provider)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return row.to_entity() if row is not None else None

    async def create_or_get(self, payment: Payment) -> Payment:
        statement = (
            select(PaymentModel)
            .where(PaymentModel.idempotency_key == payment.idempotency_key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        row = await self._db.scalar(statement)
        if row is None:
            try:
                async with self._db.db.begin_nested():
                    values = asdict(payment)
                    if values["created_at"] is None:
                        values.pop("created_at")
                    row = PaymentModel(**values)
                    self._db.add(row)
                    await self._db.flush()
            except IntegrityError as exc:
                row = await self._db.scalar(statement)
                if row is None:
                    raise InvalidPaymentStateError("cannot create payment") from exc
        return row.to_entity()

    async def save(self, payment: Payment) -> Payment:
        row = await self._db.scalar(
            select(PaymentModel)
            .where(PaymentModel.id == payment.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise PaymentNotFoundError()
        for field in (
            "status",
            "paid_amount",
            "provider_invoice_id",
            "provider_payment_id",
            "provider_transaction_id",
            "telegram_user_id",
            "checkout_url",
            "asset_code",
            "blockchain_code",
            "asset_amount",
            "asset_fee",
            "blockchain_hash",
            "sender_address",
            "expires_at",
            "paid_at",
        ):
            setattr(row, field, getattr(payment, field))
        await self._db.flush()
        return row.to_entity()

    @staticmethod
    def _unpaid_conditions() -> tuple:
        """Only rows with no financial evidence may expire or be deleted."""
        transaction_exists = (
            select(TransactionModel.id)
            .where(TransactionModel.payment_id == PaymentModel.id)
            .exists()
        )
        refund_exists = (
            select(PaymentRefundModel.id)
            .where(PaymentRefundModel.payment_id == PaymentModel.id)
            .exists()
        )
        return (
            PaymentModel.paid_at.is_(None),
            PaymentModel.paid_amount.is_(None),
            PaymentModel.provider_transaction_id.is_(None),
            PaymentModel.asset_amount.is_(None),
            PaymentModel.blockchain_hash.is_(None),
            PaymentModel.sender_address.is_(None),
            ~transaction_exists,
            ~refund_exists,
        )

    async def delete_stale(self, before: datetime, *, limit: int = 500) -> int:
        conditions = (
            PaymentModel.status.in_([PaymentStatus.EXPIRED, PaymentStatus.CANCELLED]),
            PaymentModel.updated_at <= before,
            *self._unpaid_conditions(),
        )
        stale = (
            select(PaymentModel.id)
            .where(*conditions)
            .order_by(PaymentModel.updated_at, PaymentModel.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._db.scalars(
            delete(PaymentModel)
            .where(PaymentModel.id.in_(stale), *conditions)
            .returning(PaymentModel.id)
            .execution_options(synchronize_session=False)
        )
        return len(result.all())

    async def expire_pending(self, now: datetime, *, limit: int = 500) -> int:
        conditions = (
            PaymentModel.status.in_([PaymentStatus.PENDING, PaymentStatus.PROCESSING]),
            PaymentModel.expires_at <= now,
            *self._unpaid_conditions(),
        )
        expired = (
            select(PaymentModel.id)
            .where(*conditions)
            .order_by(PaymentModel.expires_at, PaymentModel.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._db.scalars(
            update(PaymentModel)
            .where(
                PaymentModel.id.in_(expired),
                *conditions,
            )
            .values(status=PaymentStatus.EXPIRED, updated_at=now)
            .returning(PaymentModel.id)
            .execution_options(synchronize_session=False)
        )
        return len(result.all())
