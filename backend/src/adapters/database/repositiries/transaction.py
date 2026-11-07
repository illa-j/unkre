from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from adapters.database.models import PaymentModel, TransactionModel, WalletModel
from adapters.database.repositiries import CrudRepository
from adapters.database.repositiries.payment import PaymentRepository
from domain.entities.payment import CreditPurchase, Payment, Wallet
from domain.enums import PaymentStatus, TransactionType
from domain.exceptions.generation import InsufficientCreditsError
from domain.exceptions.payments import InvalidPaymentStateError
from domain.validators import NumberValidator, TextValidator
from ports import DatabaseManagerInterface


class TransactionRepository(CrudRepository[TransactionModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, TransactionModel)

    async def post_purchase(
        self, payment: Payment, wallet: Wallet, purchase: CreditPurchase
    ) -> None:
        if (
            purchase.payment_id != payment.id
            or purchase.wallet_id != wallet.id
            or payment.wallet_id != wallet.id
            or purchase.amount != payment.credits
            or purchase.balance_after != wallet.credits
        ):
            raise InvalidPaymentStateError("purchase details do not match")
        try:
            async with self._db.db.begin_nested():
                payment_row = await self._db.scalar(
                    select(PaymentModel)
                    .where(PaymentModel.id == payment.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                wallet_row = await self._db.scalar(
                    select(WalletModel)
                    .where(WalletModel.id == wallet.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if (
                    payment_row is None
                    or wallet_row is None
                    or payment_row.status
                    in (PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED)
                    or wallet_row.credits != purchase.balance_before
                    or payment_row.wallet_id != wallet.id
                    or payment_row.credits != purchase.amount
                ):
                    raise InvalidPaymentStateError("payment or wallet changed")
                await PaymentRepository(self._db).save(payment)
                wallet_row.credits = wallet.credits
                self._db.add(
                    TransactionModel(
                        id=purchase.id,
                        payment=payment_row,
                        wallet=wallet_row,
                        type=TransactionType.PURCHASE,
                        amount=purchase.amount,
                        balance_before=purchase.balance_before,
                        balance_after=purchase.balance_after,
                        idempotency_key=purchase.idempotency_key,
                    )
                )
                await self._db.flush()
        except IntegrityError as exc:
            raise InvalidPaymentStateError(
                "provider transaction is already recorded"
            ) from exc

    async def post_adjustment(
        self,
        wallet: Wallet,
        *,
        amount: int,
        idempotency_key: str,
        description: str | None = None,
    ) -> Wallet:
        amount = NumberValidator.validate_integer(
            amount, min_value=-(2**63 - 1), max_value=2**63 - 1
        )
        if amount == 0:
            raise InvalidPaymentStateError("adjustment amount cannot be zero")
        idempotency_key = TextValidator.validate(
            idempotency_key, max_length=255, strip=True
        )
        description = TextValidator.validate(
            description, max_length=4096, nullable=True
        )
        try:
            async with self._db.db.begin_nested():
                wallet_row = await self._db.scalar(
                    select(WalletModel)
                    .where(WalletModel.id == wallet.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if wallet_row is None or wallet_row.credits != wallet.credits:
                    raise InvalidPaymentStateError("wallet changed")
                after = NumberValidator.validate_integer(
                    wallet.credits + amount, min_value=0, max_value=2**63 - 1
                )
                wallet_row.credits = after
                self._db.add(
                    TransactionModel(
                        wallet=wallet_row,
                        type=TransactionType.ADJUSTMENT,
                        amount=amount,
                        balance_before=wallet.credits,
                        balance_after=after,
                        idempotency_key=idempotency_key,
                        description=description,
                    )
                )
                await self._db.flush()
        except IntegrityError as exc:
            raise InvalidPaymentStateError(
                "adjustment is already recorded"
            ) from exc
        return Wallet(
            id=wallet.id,
            user_id=wallet.user_id,
            credits=wallet.credits + amount,
        )

    async def post_spend(
        self,
        wallet: Wallet,
        *,
        amount: int,
        generation_id: UUID,
        idempotency_key: str,
        description: str | None = None,
    ) -> Wallet:
        amount = NumberValidator.validate_integer(
            amount, min_value=1, max_value=2**63 - 1
        )
        idempotency_key = TextValidator.validate(
            idempotency_key, max_length=255, strip=True
        )
        description = TextValidator.validate(
            description, max_length=4096, nullable=True
        )
        try:
            async with self._db.db.begin_nested():
                wallet_row = await self._db.scalar(
                    select(WalletModel)
                    .where(WalletModel.id == wallet.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if wallet_row is None or wallet_row.credits != wallet.credits:
                    raise InvalidPaymentStateError("wallet changed")
                if wallet.credits < amount:
                    raise InsufficientCreditsError(amount, wallet.credits)
                after = wallet.credits - amount
                wallet_row.credits = after
                self._db.add(
                    TransactionModel(
                        wallet=wallet_row,
                        type=TransactionType.SPEND,
                        amount=-amount,
                        balance_before=wallet.credits,
                        balance_after=after,
                        idempotency_key=idempotency_key,
                        description=description,
                        generation_id=generation_id,
                    )
                )
                await self._db.flush()
        except IntegrityError as exc:
            raise InvalidPaymentStateError(
                "generation charge is already recorded"
            ) from exc
        return Wallet(
            id=wallet.id,
            user_id=wallet.user_id,
            credits=wallet.credits - amount,
        )
