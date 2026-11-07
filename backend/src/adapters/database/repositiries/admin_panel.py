from datetime import datetime
from uuid import UUID

from sqlalchemy import String, cast, func, or_, select

from adapters.database.models import (
    AdminModel,
    GenerationModel,
    PaymentModel,
    PromoRedemptionModel,
    TransactionModel,
    UserModel,
    WalletModel,
    WorkflowModel,
)
from domain.enums import (
    GenerationStatus,
    PaymentProvider,
    PaymentStatus,
    TransactionType,
)
from ports import DatabaseManagerInterface

ACTIVE_STATUSES = (
    GenerationStatus.PENDING,
    GenerationStatus.QUEUED,
    GenerationStatus.PROCESSING,
)


class AdminPanelRepository:
    """Read models for the admin panel; writes go through the regular repositories."""

    def __init__(self, db: DatabaseManagerInterface) -> None:
        self._db = db

    async def totals(self) -> dict[str, int]:
        generation_counts = select(
            GenerationModel.status, func.count(GenerationModel.id)
        ).group_by(GenerationModel.status)
        statement = select(
            select(func.count(UserModel.id)).scalar_subquery().label("users_total"),
            select(func.count(UserModel.id))
            .where(UserModel.is_blocked.is_(True))
            .scalar_subquery()
            .label("users_blocked"),
            select(func.count(GenerationModel.id))
            .scalar_subquery()
            .label("generations_total"),
            select(func.count(PromoRedemptionModel.id))
            .scalar_subquery()
            .label("promo_redemptions"),
            select(func.count(PaymentModel.id))
            .where(PaymentModel.status == PaymentStatus.PENDING)
            .scalar_subquery()
            .label("payments_pending"),
            select(func.coalesce(func.sum(TransactionModel.amount), 0))
            .where(TransactionModel.type == TransactionType.SPEND)
            .scalar_subquery()
            .label("credits_spent_total"),
        )
        row = (await self._db.execute(statement)).one()
        totals = {key: int(value or 0) for key, value in row._mapping.items()}
        rows = (await self._db.execute(generation_counts)).all()
        totals["generations_by_status"] = {
            str(getattr(status, "value", status)): int(count) for status, count in rows
        }
        return totals

    async def activity_since(self, since: datetime) -> tuple[list[datetime], list[datetime], list[tuple[datetime, int]]]:
        users = await self._timestamps(select(UserModel.created_at).where(UserModel.created_at >= since))
        generations = await self._timestamps(
            select(GenerationModel.created_at).where(GenerationModel.created_at >= since)
        )
        spend_rows = (
            await self._db.execute(
                select(TransactionModel.created_at, TransactionModel.amount).where(
                    TransactionModel.created_at >= since,
                    TransactionModel.type == TransactionType.SPEND,
                )
            )
        ).all()
        spend = [(created_at, int(amount)) for created_at, amount in spend_rows]
        return users, generations, spend

    async def _timestamps(self, statement) -> list[datetime]:
        return [row[0] for row in (await self._db.execute(statement)).all()]

    async def revenue(self, since: datetime | None) -> tuple[str, int]:
        statement = select(
            func.coalesce(func.sum(PaymentModel.paid_amount), 0),
            func.coalesce(func.sum(PaymentModel.credits), 0),
        ).where(PaymentModel.status == PaymentStatus.SUCCEEDED)
        if since is not None:
            statement = statement.where(PaymentModel.paid_at >= since)
        paid, credits = (await self._db.execute(statement)).one()
        return str(paid or "0"), int(credits or 0)

    async def users_since(self, since: datetime) -> int:
        return int(
            await self._db.scalar(
                select(func.count(UserModel.id)).where(UserModel.created_at >= since)
            )
            or 0
        )

    async def generations_since(self, since: datetime) -> int:
        return int(
            await self._db.scalar(
                select(func.count(GenerationModel.id)).where(
                    GenerationModel.created_at >= since
                )
            )
            or 0
        )

    async def active_generations(self) -> int:
        return int(
            await self._db.scalar(
                select(func.count(GenerationModel.id)).where(
                    GenerationModel.status.in_(ACTIVE_STATUSES)
                )
            )
            or 0
        )

    async def credits_spent_since(self, since: datetime) -> int:
        value = await self._db.scalar(
            select(func.coalesce(func.sum(TransactionModel.amount), 0)).where(
                TransactionModel.created_at >= since,
                TransactionModel.type == TransactionType.SPEND,
            )
        )
        return -int(value or 0)

    async def users(
        self,
        *,
        query: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple], int]:
        conditions = self._user_conditions(query, status)
        generations = (
            select(func.count(GenerationModel.id))
            .where(GenerationModel.user_id == UserModel.id)
            .correlate(UserModel)
            .scalar_subquery()
        )
        spent = (
            select(func.coalesce(func.sum(TransactionModel.amount), 0))
            .join(WalletModel, WalletModel.id == TransactionModel.wallet_id)
            .where(
                WalletModel.user_id == UserModel.id,
                TransactionModel.type == TransactionType.SPEND,
            )
            .correlate(UserModel)
            .scalar_subquery()
        )
        statement = (
            select(
                UserModel,
                func.coalesce(WalletModel.credits, 0).label("credits"),
                generations.label("generations"),
                spent.label("spent"),
            )
            .outerjoin(WalletModel, WalletModel.user_id == UserModel.id)
            .where(*conditions)
            .order_by(UserModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._db.execute(statement)).all()
        total = int(
            await self._db.scalar(select(func.count(UserModel.id)).where(*conditions)) or 0
        )
        return [tuple(row) for row in rows], total

    def _user_conditions(self, query: str | None, status: str | None) -> list:
        conditions = []
        if query:
            needle = f"%{query.strip().lower()}%"
            conditions.append(
                or_(
                    func.lower(UserModel.first_name).like(needle),
                    func.lower(UserModel.last_name).like(needle),
                    func.lower(UserModel.username).like(needle),
                    func.lower(UserModel.google_email).like(needle),
                    cast(UserModel.telegram_id, String).like(f"%{query.strip()}%"),
                )
            )
        if status == "blocked":
            conditions.append(UserModel.is_blocked.is_(True))
        elif status == "active":
            conditions.append(UserModel.is_blocked.is_(False))
        return conditions

    async def generations(
        self,
        *,
        status: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple], int]:
        conditions = []
        if status:
            try:
                conditions.append(GenerationModel.status == GenerationStatus(status))
            except ValueError:
                conditions.append(GenerationModel.status == GenerationStatus.PENDING)
        if query:
            needle = f"%{query.strip().lower()}%"
            conditions.append(
                or_(
                    func.lower(GenerationModel.prompt).like(needle),
                    func.lower(UserModel.first_name).like(needle),
                    func.lower(UserModel.username).like(needle),
                    func.lower(UserModel.google_email).like(needle),
                )
            )
        statement = (
            select(
                GenerationModel,
                UserModel.id.label("user_id"),
                UserModel.first_name,
                UserModel.last_name,
                UserModel.username,
                UserModel.google_email,
                WorkflowModel.name.label("workflow"),
            )
            .join(UserModel, UserModel.id == GenerationModel.user_id)
            .join(WorkflowModel, WorkflowModel.id == GenerationModel.workflow_id)
            .where(*conditions)
            .order_by(GenerationModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._db.execute(statement)).all()
        total = int(
            await self._db.scalar(
                select(func.count(GenerationModel.id))
                .join(UserModel, UserModel.id == GenerationModel.user_id)
                .where(*conditions)
            )
            or 0
        )
        return [tuple(row) for row in rows], total

    async def payments(
        self,
        *,
        status: str | None,
        provider: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple], int]:
        conditions = []
        if status:
            try:
                conditions.append(PaymentModel.status == PaymentStatus(status))
            except ValueError:
                pass
        if provider:
            try:
                conditions.append(PaymentModel.provider == PaymentProvider(provider))
            except ValueError:
                pass
        statement = (
            select(
                PaymentModel,
                UserModel.id.label("user_id"),
                UserModel.first_name,
                UserModel.last_name,
                UserModel.username,
            )
            .join(WalletModel, WalletModel.id == PaymentModel.wallet_id)
            .join(UserModel, UserModel.id == WalletModel.user_id)
            .where(*conditions)
            .order_by(PaymentModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._db.execute(statement)).all()
        total = int(
            await self._db.scalar(
                select(func.count(PaymentModel.id))
                .join(WalletModel, WalletModel.id == PaymentModel.wallet_id)
                .where(*conditions)
            )
            or 0
        )
        return [tuple(row) for row in rows], total

    async def promo_redemptions(
        self, promo_code_id: UUID, *, limit: int, offset: int
    ) -> tuple[list[tuple], int]:
        statement = (
            select(
                PromoRedemptionModel,
                UserModel.id.label("user_id"),
                UserModel.first_name,
                UserModel.last_name,
                UserModel.username,
                UserModel.google_email,
            )
            .join(UserModel, UserModel.id == PromoRedemptionModel.user_id)
            .where(PromoRedemptionModel.promo_code_id == promo_code_id)
            .order_by(PromoRedemptionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._db.execute(statement)).all()
        total = int(
            await self._db.scalar(
                select(func.count(PromoRedemptionModel.id)).where(
                    PromoRedemptionModel.promo_code_id == promo_code_id
                )
            )
            or 0
        )
        return [tuple(row) for row in rows], total

    async def admin(self, admin_id: UUID) -> AdminModel | None:
        return await self._db.get(AdminModel, admin_id)

    async def admins(self) -> list[AdminModel]:
        return list(
            (
                await self._db.scalars(
                    select(AdminModel).order_by(AdminModel.created_at.asc())
                )
            ).all()
        )
