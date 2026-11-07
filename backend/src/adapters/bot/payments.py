"""Telegram Stars payment handlers for the long-polling bot.

The API webhook endpoint exists, but a bot can use either getUpdates or a
webhook, not both. UNKRE already runs the bot in polling mode, so payment
updates are handled here instead of asking Telegram to deliver them to the API.
"""

from datetime import timedelta
from logging import getLogger

from aiogram import Bot, F, Router
from aiogram.types import Message, PreCheckoutQuery

from adapters.database import DatabaseManager, session_scope
from adapters.database.repositiries import (
    PaymentRepository,
    ReferralRepository,
    TransactionRepository,
    UserRepository,
    WalletRepository,
)
from adapters.settings import Settings
from adapters.system_settings import build_system_settings
from domain.services.referral import ReferralService
from domain.services.telegram_stars_payment import TelegramStarsPaymentService

logger = getLogger(__name__)


async def stars_service(session, bot: Bot, settings: Settings) -> TelegramStarsPaymentService:
    manager = DatabaseManager(session)
    system_settings = build_system_settings(manager, settings)
    referrals = ReferralService(
        ReferralRepository(manager),
        WalletRepository(manager),
        TransactionRepository(manager),
        inviter_credits=await system_settings.get_int("referral.inviter_credits"),
        invitee_credits=await system_settings.get_int("referral.invitee_credits"),
    )
    return TelegramStarsPaymentService(
        PaymentRepository(manager),
        WalletRepository(manager),
        TransactionRepository(manager),
        UserRepository(manager),
        bot,
        invoice_ttl=timedelta(
            seconds=settings.PAYMENT_SETTINGS.PAYMENT_INVOICE_TTL_SECONDS
        ),
        referrals=referrals,
    )


def build_payment_router(*, bot: Bot, settings: Settings) -> Router:
    router = Router(name="stars-payments")

    @router.pre_checkout_query()
    async def handle_pre_checkout(query: PreCheckoutQuery) -> None:
        ok = True
        try:
            async with session_scope() as session:
                service = await stars_service(session, bot, settings)
                await service.validate_pre_checkout(query)
        except Exception:
            logger.exception("Telegram Stars pre-checkout failed")
            ok = False
        await query.answer(
            ok=ok,
            error_message=None if ok else "Invoice is unavailable or payment details do not match",
        )

    @router.message(F.successful_payment)
    async def handle_successful_payment(message: Message) -> None:
        credited = False
        try:
            async with session_scope() as session:
                service = await stars_service(session, bot, settings)
                credited = await service.handle_successful_payment(message)
        except Exception:
            logger.exception("Telegram Stars payment settlement failed")
            return
        if credited:
            await message.answer("Payment received — your credits are ready.")

    return router
