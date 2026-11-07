from unittest.mock import AsyncMock, Mock

import pytest
from aiogram.types import InlineKeyboardMarkup, Message, WebAppInfo
from pydantic import ValidationError

from adapters.bot.handlers import send_start, start_keyboard
from adapters.bot.texts import BRAND, BUTTON_LABEL, start_message
from adapters.settings import BotSettings

MINIAPP = "https://unkre.com/studio"


def fake_message() -> Mock:
    message = Mock(spec=Message)
    message.answer = AsyncMock()
    return message


async def test_start_replies_with_brand_description_and_miniapp_button():
    message = fake_message()

    await send_start(message, miniapp_url=MINIAPP, free_credits=15)

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.await_args
    text = args[0]
    assert BRAND in text
    assert "Krea 2" in text
    assert "Qwen Image 2.1" in text
    assert "18+" not in text
    assert "15 free credits" in text
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["disable_web_page_preview"] is True

    markup: InlineKeyboardMarkup = kwargs["reply_markup"]
    button = markup.inline_keyboard[0][0]
    assert button.text == BUTTON_LABEL
    assert button.web_app is not None
    assert button.web_app.url == MINIAPP


def test_keyboard_uses_a_web_app_button():
    markup = start_keyboard(MINIAPP)

    assert isinstance(markup.inline_keyboard[0][0].web_app, WebAppInfo)
    assert markup.inline_keyboard[0][0].web_app.url == MINIAPP


def test_start_message_without_free_credits_avoids_the_offer():
    text = start_message(0)

    assert "free credits" not in text
    assert "Create an account in seconds" in text


def test_miniapp_url_requires_https_outside_localhost():
    assert BotSettings(TELEGRAM_MINIAPP_URL=MINIAPP).TELEGRAM_MINIAPP_URL == MINIAPP
    assert (
        BotSettings(TELEGRAM_MINIAPP_URL="http://localhost:3000/studio").TELEGRAM_MINIAPP_URL
        == "http://localhost:3000/studio"
    )
    with pytest.raises(ValidationError):
        BotSettings(TELEGRAM_MINIAPP_URL="http://example.com/studio")


def test_bot_is_ready_only_with_token_and_url():
    assert BotSettings(TELEGRAM_BOT_TOKEN="", TELEGRAM_MINIAPP_URL=MINIAPP).ready is False
    assert BotSettings(TELEGRAM_BOT_TOKEN="token", TELEGRAM_MINIAPP_URL="").ready is False
    assert BotSettings(TELEGRAM_BOT_TOKEN="token", TELEGRAM_MINIAPP_URL=MINIAPP).ready is True
