from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid7

from adapters.api.schemas.admin_panel import (
    AdjustCreditsResponse,
    AdminGenerationItem,
    AdminGenerationPage,
    AdminOverviewResponse,
    AdminPaymentItem,
    AdminPaymentPage,
    AdminRedemptionItem,
    AdminRedemptionPage,
    AdminUserItem,
    AdminUserPage,
    OverviewPoint,
)
from adapters.database.repositiries.admin_panel import AdminPanelRepository
from adapters.database.repositiries.transaction import TransactionRepository
from adapters.database.repositiries.user import UserRepository
from adapters.database.repositiries.wallet import WalletRepository


class AdminPanelService:
    def __init__(
        self,
        panel: AdminPanelRepository,
        users: UserRepository,
        wallets: WalletRepository,
        transactions: TransactionRepository,
    ) -> None:
        self._panel = panel
        self._users = users
        self._wallets = wallets
        self._transactions = transactions

    async def overview(self) -> AdminOverviewResponse:
        now = datetime.now(UTC)
        totals = await self._panel.totals()
        start = (now - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
        users, generations, spend = await self._panel.activity_since(start)
        buckets: dict[date, dict[str, int]] = defaultdict(
            lambda: {"users": 0, "generations": 0, "credits_spent": 0}
        )
        for created_at in users:
            buckets[_day(created_at)]["users"] += 1
        for created_at in generations:
            buckets[_day(created_at)]["generations"] += 1
        for created_at, amount in spend:
            buckets[_day(created_at)]["credits_spent"] -= amount
        daily = [
            OverviewPoint(
                date=(start + timedelta(days=index)).date(),
                users=buckets[(start + timedelta(days=index)).date()]["users"],
                generations=buckets[(start + timedelta(days=index)).date()]["generations"],
                credits_spent=buckets[(start + timedelta(days=index)).date()]["credits_spent"],
            )
            for index in range(14)
        ]
        revenue_total, _ = await self._panel.revenue(None)
        revenue_30d, credits_30d = await self._panel.revenue(now - timedelta(days=30))
        return AdminOverviewResponse(
            users_total=totals["users_total"],
            users_blocked=totals["users_blocked"],
            users_new_24h=await self._panel.users_since(now - timedelta(days=1)),
            users_new_7d=await self._panel.users_since(now - timedelta(days=7)),
            users_new_30d=await self._panel.users_since(now - timedelta(days=30)),
            generations_total=totals["generations_total"],
            generations_24h=await self._panel.generations_since(now - timedelta(days=1)),
            generations_7d=await self._panel.generations_since(now - timedelta(days=7)),
            generations_active=await self._panel.active_generations(),
            generations_by_status=totals["generations_by_status"],
            credits_spent_24h=await self._panel.credits_spent_since(now - timedelta(days=1)),
            credits_spent_7d=await self._panel.credits_spent_since(now - timedelta(days=7)),
            revenue_total=_money(revenue_total),
            revenue_30d=_money(revenue_30d),
            credits_sold_30d=credits_30d,
            payments_pending=totals["payments_pending"],
            promo_redemptions=totals["promo_redemptions"],
            daily=daily,
        )

    async def users(
        self, *, query: str | None, status: str | None, limit: int, offset: int
    ) -> AdminUserPage:
        rows, total = await self._panel.users(
            query=query, status=status, limit=limit, offset=offset
        )
        return AdminUserPage(
            total=total,
            items=[
                AdminUserItem(
                    id=user.id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    username=user.username,
                    google_email=user.google_email,
                    telegram_id=user.telegram_id,
                    photo_url=user.photo_url,
                    credits=int(credits or 0),
                    is_blocked=user.is_blocked,
                    registered_at=user.created_at,
                    last_active_at=user.last_active_at,
                    generations=int(generations or 0),
                    credits_spent=-int(spent or 0),
                )
                for user, credits, generations, spent in rows
            ],
        )

    async def set_blocked(self, user_id: UUID, blocked: bool) -> bool:
        updated = await self._users.update(user_id, {"is_blocked": blocked})
        return updated is not None

    async def adjust_credits(
        self, user_id: UUID, amount: int, description: str
    ) -> AdjustCreditsResponse | None:
        wallet = await self._wallets.get_by_user(user_id)
        if wallet is None:
            return None
        updated = await self._transactions.post_adjustment(
            wallet,
            amount=amount,
            idempotency_key=f"admin:{uuid7()}",
            description=description,
        )
        return AdjustCreditsResponse(user_id=user_id, credits=updated.credits)

    async def generations(
        self, *, status: str | None, query: str | None, limit: int, offset: int
    ) -> AdminGenerationPage:
        rows, total = await self._panel.generations(
            status=status, query=query, limit=limit, offset=offset
        )
        items = []
        for generation, user_id, first_name, last_name, username, email, workflow in rows:
            items.append(
                AdminGenerationItem(
                    id=generation.id,
                    user_id=user_id,
                    user_name=_display_name(first_name, last_name, username),
                    user_email=email,
                    workflow=workflow,
                    prompt=generation.prompt,
                    status=str(getattr(generation.status, "value", generation.status)),
                    credits_spent=generation.credits_spent,
                    seed=generation.seed,
                    error=generation.error,
                    created_at=generation.created_at,
                    completed_at=generation.completed_at,
                )
            )
        return AdminGenerationPage(items=items, total=total)

    async def payments(
        self, *, status: str | None, provider: str | None, limit: int, offset: int
    ) -> AdminPaymentPage:
        rows, total = await self._panel.payments(
            status=status, provider=provider, limit=limit, offset=offset
        )
        return AdminPaymentPage(
            total=total,
            items=[
                AdminPaymentItem(
                    id=payment.id,
                    user_id=user_id,
                    user_name=_display_name(first_name, last_name, username),
                    provider=str(getattr(payment.provider, "value", payment.provider)),
                    status=str(getattr(payment.status, "value", payment.status)),
                    credits=payment.credits,
                    amount=_money(payment.amount),
                    paid_amount=_money(payment.paid_amount) if payment.paid_amount is not None else None,
                    currency=payment.currency,
                    created_at=payment.created_at,
                    paid_at=payment.paid_at,
                )
                for payment, user_id, first_name, last_name, username in rows
            ],
        )

    async def redemptions(
        self, promo_code_id: UUID, *, limit: int, offset: int
    ) -> AdminRedemptionPage:
        rows, total = await self._panel.promo_redemptions(
            promo_code_id, limit=limit, offset=offset
        )
        return AdminRedemptionPage(
            total=total,
            items=[
                AdminRedemptionItem(
                    id=redemption.id,
                    user_id=user_id,
                    user_name=_display_name(first_name, last_name, username),
                    user_email=email,
                    credits=redemption.credits,
                    created_at=redemption.created_at,
                )
                for redemption, user_id, first_name, last_name, username, email in rows
            ],
        )


def _day(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.date()


def _money(value: Decimal | str | None) -> str:
    if value is None:
        return "0.00"
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def _display_name(
    first_name: str | None, last_name: str | None, username: str | None
) -> str:
    name = " ".join(part for part in (first_name, last_name) if part).strip()
    if name:
        return name
    return f"@{username}" if username else "Unknown user"
