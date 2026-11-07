"""Run the public Telegram bot with long polling.

    python -m adapters.bot.main

The process exits cleanly when TELEGRAM_BOT_TOKEN or TELEGRAM_MINIAPP_URL is
missing, so a disabled bot never loops in a restart cycle.
"""

import asyncio
from logging import INFO, basicConfig, getLogger

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from sqlalchemy.exc import SQLAlchemyError

from adapters.bot.handlers import build_router
from adapters.bot.payments import build_payment_router
from adapters.database import DatabaseManager, session_scope
from adapters.settings import Settings, get_settings
from adapters.system_settings import build_system_settings

logger = getLogger(__name__)


async def initial_credits(settings: Settings) -> int:
    """Prefer the admin override so the offer matches what a new account gets."""
    try:
        async with session_scope() as session:
            return await build_system_settings(
                DatabaseManager(session), settings
            ).get_int("registration.initial_credits")
    except (SQLAlchemyError, OSError):
        logger.warning(
            "Could not read registration.initial_credits; using the env default"
        )
        return settings.AUTH_SETTINGS.USER_INITIAL_CREDITS


async def run() -> None:
    settings = get_settings()
    config = settings.BOT_SETTINGS
    if not config.authenticated:
        logger.warning("TELEGRAM_BOT_TOKEN is not configured; bot disabled")
        return
    if not config.TELEGRAM_MINIAPP_URL:
        logger.error("TELEGRAM_MINIAPP_URL is not configured; bot disabled")
        return

    session = AiohttpSession(
        timeout=settings.PAYMENT_SETTINGS.PAYMENT_PROVIDER_TIMEOUT_SECONDS
    )
    bot = Bot(
        config.TELEGRAM_BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(
        build_router(
            miniapp_url=config.TELEGRAM_MINIAPP_URL,
            free_credits=await initial_credits(settings),
        )
    )
    dispatcher.include_router(build_payment_router(bot=bot, settings=settings))
    try:
        await bot.delete_webhook()
        logger.info("UNKRE bot is polling for updates")
        await dispatcher.start_polling(
            bot,
            polling_timeout=config.TELEGRAM_BOT_POLLING_TIMEOUT,
            allowed_updates=["message", "pre_checkout_query"],
        )
    finally:
        await bot.session.close()


def main() -> None:
    basicConfig(level=INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    main()
