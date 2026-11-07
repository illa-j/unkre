from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from adapters.bot.texts import BUTTON_LABEL, start_message


def start_keyboard(miniapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BUTTON_LABEL,
                    web_app=WebAppInfo(url=miniapp_url),
                )
            ]
        ]
    )


async def send_start(
    message: Message, *, miniapp_url: str, free_credits: int
) -> None:
    await message.answer(
        start_message(free_credits),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=start_keyboard(miniapp_url),
    )


def build_router(*, miniapp_url: str, free_credits: int) -> Router:
    router = Router(name="start")

    @router.message(CommandStart())
    async def handle_start(message: Message) -> None:
        await send_start(message, miniapp_url=miniapp_url, free_credits=free_credits)

    return router
