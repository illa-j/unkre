from decimal import Decimal, localcontext
from typing import Annotated
from uuid import UUID

from aiogram.types import Update
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError

from adapters.api.dependencies.payment import (
    AtlosSignatureDep,
    CryptoPaymentServiceDep,
    PaymentServiceDep,
    StarsPaymentServiceDep,
    verify_payment_origin,
    verify_telegram_payment_webhook,
)
from adapters.api.dependencies.system_setting import SystemSettingsServiceDep
from adapters.api.dependencies.user import CurrentUserDep
from adapters.api.schemas.payment import (
    CreatePaymentRequest,
    PaymentPricesResponse,
    PaymentResponse,
    TelegramPaymentUpdateRequest,
)
from domain.entities.payment import Payment
from domain.exceptions.auth import UserBlockedError
from domain.exceptions.payments import (
    InvalidPaymentAmountError,
    InvalidPaymentStateError,
    PaymentProviderError,
)
from domain.validators import PaymentAmountValidator

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/prices", response_model=PaymentPricesResponse)
async def get_payment_prices(
    user: CurrentUserDep, system_settings: SystemSettingsServiceDep
) -> PaymentPricesResponse:
    crypto_min_amount = await system_settings.get_decimal(
        "payments.crypto_min_amount"
    )
    return PaymentPricesResponse(
        crypto_price_per_credit=await system_settings.get_decimal(
            "payments.crypto_price_per_credit"
        ),
        crypto_currency=await system_settings.get_str("payments.crypto_currency"),
        stars_price_per_credit=await system_settings.get_optional_int(
            "payments.stars_price_per_credit"
        ),
        crypto_min_amount=crypto_min_amount or Decimal("0"),
        stars_min_amount=await system_settings.get_int("payments.stars_min_amount"),
    )


@router.post(
    "/crypto",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_payment_origin)],
)
async def create_crypto_payment(
    data: CreatePaymentRequest,
    user: CurrentUserDep,
    service: CryptoPaymentServiceDep,
    system_settings: SystemSettingsServiceDep,
) -> Payment:
    price = await system_settings.get_decimal("payments.crypto_price_per_credit")
    currency = await system_settings.get_str("payments.crypto_currency")
    if price is None:
        raise PaymentProviderError("Crypto credit price is not configured")
    with localcontext() as context:
        context.prec = 80
        amount = price * data.credits
    amount = PaymentAmountValidator.validate(amount)
    minimum = await system_settings.get_decimal("payments.crypto_min_amount")
    if minimum is not None and amount < minimum:
        raise InvalidPaymentAmountError(
            f"minimum crypto payment is {minimum.normalize()} {currency}"
        )
    return await service.create_invoice(
        user.id,
        credits=data.credits,
        amount=amount,
        currency=currency,
        idempotency_key=data.idempotency_key,
    )


@router.post(
    "/stars",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_payment_origin)],
)
async def create_stars_payment(
    data: CreatePaymentRequest,
    user: CurrentUserDep,
    service: StarsPaymentServiceDep,
    system_settings: SystemSettingsServiceDep,
) -> Payment:
    price = await system_settings.get_optional_int(
        "payments.stars_price_per_credit"
    )
    if price is None:
        raise PaymentProviderError("Stars credit price is not configured")
    stars = price * data.credits
    minimum = await system_settings.get_int("payments.stars_min_amount")
    if stars < minimum:
        raise InvalidPaymentAmountError(
            f"minimum Telegram Stars payment is {minimum} Stars"
        )
    return await service.create_invoice(
        user.id,
        credits=data.credits,
        stars=stars,
        idempotency_key=data.idempotency_key,
    )


@router.get("", response_model=list[PaymentResponse])
async def get_payments(
    user: CurrentUserDep,
    service: PaymentServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Payment]:
    return await service.get_payments(user.id, limit=limit, offset=offset)


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID, user: CurrentUserDep, service: PaymentServiceDep
) -> Payment:
    return await service.get_payment(user.id, payment_id)


@router.post("/webhooks/atlos")
async def atlos_payment_webhook(
    request: Request, signature: AtlosSignatureDep, service: CryptoPaymentServiceDep
) -> dict[str, bool]:
    credited = await service.handle_postback(await request.body(), signature)
    return {"ok": True, "credited": credited}


@router.post(
    "/webhooks/telegram", dependencies=[Depends(verify_telegram_payment_webhook)]
)
async def telegram_payment_webhook(
    data: TelegramPaymentUpdateRequest, service: StarsPaymentServiceDep
) -> dict[str, object]:
    try:
        update = Update.model_validate(data.model_dump(exclude_none=True))
    except PydanticValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    if update.pre_checkout_query is not None:
        query = update.pre_checkout_query
        result = {"method": "answerPreCheckoutQuery", "pre_checkout_query_id": query.id}
        try:
            await service.validate_pre_checkout(query)
        except InvalidPaymentStateError, UserBlockedError:
            return {
                **result,
                "ok": False,
                "error_message": "Invoice is unavailable or payment details do not match",
            }
        # The function-scoped database dependency commits before this approval is sent.
        return {**result, "ok": True}
    if update.message is not None and update.message.successful_payment is not None:
        await service.handle_successful_payment(update.message)
    return {"ok": True}
