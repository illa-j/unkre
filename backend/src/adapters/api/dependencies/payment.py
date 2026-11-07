import hmac
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Annotated

import httpx
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from fastapi import Depends, Header, HTTPException, Request, status

from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.api.dependencies.settings import SettingsDep
from adapters.api.dependencies.user import ReferralServiceDep
from adapters.database.repositiries import (
    PaymentRepository,
    TransactionRepository,
    UserRepository,
    WalletRepository,
)
from domain.enums import PaymentProvider
from domain.exceptions.payments import PaymentProviderError
from domain.services.crypto_payment import CryptoPaymentService
from domain.services.payment import PaymentService
from domain.services.telegram_stars_payment import TelegramStarsPaymentService


async def get_payment_service(
    provider: PaymentProvider,
    manager: DatabaseManagerDep,
    referrals: ReferralServiceDep,
) -> PaymentService:
    return PaymentService(
        PaymentRepository(manager),
        WalletRepository(manager),
        TransactionRepository(manager),
        UserRepository(manager),
        provider,
        referrals=referrals,
    )


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]


async def get_payment_http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


PaymentHttpClientDep = Annotated[
    httpx.AsyncClient, Depends(get_payment_http_client, scope="function")
]


async def get_payment_bot(settings: SettingsDep) -> AsyncIterator[Bot]:
    config = settings.PAYMENT_SETTINGS
    if not config.TELEGRAM_BOT_TOKEN:
        raise PaymentProviderError("Telegram payments are not configured")
    bot = Bot(
        config.TELEGRAM_BOT_TOKEN,
        session=AiohttpSession(timeout=config.PAYMENT_PROVIDER_TIMEOUT_SECONDS),
    )
    try:
        yield bot
    finally:
        await bot.session.close()


PaymentBotDep = Annotated[Bot, Depends(get_payment_bot, scope="function")]


async def get_crypto_payment_service(
    manager: DatabaseManagerDep,
    client: PaymentHttpClientDep,
    settings: SettingsDep,
    referrals: ReferralServiceDep,
) -> CryptoPaymentService:
    config = settings.PAYMENT_SETTINGS
    if not config.ATLOS_MERCHANT_ID or not config.ATLOS_API_SECRET:
        raise PaymentProviderError("Crypto payments are not configured")
    return CryptoPaymentService(
        PaymentRepository(manager),
        WalletRepository(manager),
        TransactionRepository(manager),
        UserRepository(manager),
        client,
        merchant_id=config.ATLOS_MERCHANT_ID,
        api_secret=config.ATLOS_API_SECRET,
        invoice_ttl=timedelta(seconds=config.PAYMENT_INVOICE_TTL_SECONDS),
        timeout=config.PAYMENT_PROVIDER_TIMEOUT_SECONDS,
        referrals=referrals,
        postback_url=config.PAYMENT_POSTBACK_URL,
    )


CryptoPaymentServiceDep = Annotated[
    CryptoPaymentService, Depends(get_crypto_payment_service)
]


async def get_stars_payment_service(
    manager: DatabaseManagerDep,
    bot: PaymentBotDep,
    settings: SettingsDep,
    referrals: ReferralServiceDep,
) -> TelegramStarsPaymentService:
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


StarsPaymentServiceDep = Annotated[
    TelegramStarsPaymentService, Depends(get_stars_payment_service)
]


async def verify_telegram_payment_webhook(
    settings: SettingsDep,
    secret: Annotated[
        str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")
    ] = None,
) -> None:
    expected = settings.PAYMENT_SETTINGS.TELEGRAM_WEBHOOK_SECRET
    if not expected:
        raise PaymentProviderError("Telegram payment webhook is not configured")
    if secret is None or not hmac.compare_digest(secret.encode(), expected.encode()):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Invalid Telegram webhook secret"
        )


async def get_atlos_signature(
    signature: Annotated[str | None, Header(alias="Signature")] = None,
) -> str:
    if not signature:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing payment signature")
    return signature


AtlosSignatureDep = Annotated[str, Depends(get_atlos_signature)]


async def verify_payment_origin(request: Request, settings: SettingsDep) -> None:
    if not settings.API_SETTINGS.CSRF_ENABLED:
        return
    origin = request.headers.get("origin")
    allowed = {str(request.base_url).rstrip("/")}
    allowed.update(
        value.strip().rstrip("/")
        for value in settings.API_SETTINGS.CORS_ALLOWED_ORIGINS.split(",")
        if value.strip()
    )
    if (origin is not None and origin.rstrip("/") not in allowed) or (
        origin is None and request.headers.get("sec-fetch-site") == "cross-site"
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Payment request origin is not allowed"
        )
