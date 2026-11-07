import hmac
import logging

from aiogram.exceptions import TelegramAPIError
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from adapters.api.cookies import create_csrf_token, get_csrf_token, set_csrf_cookie
from adapters.settings import Settings
from domain.exceptions.auth import (
    AccountLinkConflictError,
    AuthenticationConflictError,
    AuthenticationError,
    AuthProviderUnavailableError,
    UserBlockedError,
)
from domain.exceptions.generation import (
    GenerationNotFoundError,
    InsufficientCreditsError,
    InvalidGenerationStateError,
    WorkflowNotFoundError,
)
from domain.exceptions.payments import (
    InvalidPaymentSignatureError,
    InvalidPaymentStateError,
    PaymentNotFoundError,
    PaymentProviderError,
)
from domain.exceptions.preset import PresetNotFoundError
from domain.exceptions.promo import (
    InvalidPromoCodeError,
    PromoCodeConflictError,
    PromoCodeError,
    PromoCodeNotFoundError,
)
from domain.exceptions.runpod import RunPodError
from domain.exceptions.system_setting import UnknownSystemSettingError
from domain.exceptions.validation import ValidationError

PAYMENT_WEBHOOK_PATHS = frozenset(
    {"/payments/webhooks/atlos", "/payments/webhooks/telegram"}
)
# The MiniApp authenticates with Telegram-signed initData, not ambient
# cookies, so CSRF tokens do not apply to this endpoint.
MINIAPP_AUTH_PATHS = frozenset({"/users/auth/telegram-webapp"})
logger = logging.getLogger(__name__)


async def csrf_middleware(
    request: Request, call_next: RequestResponseEndpoint, *, settings: Settings
) -> Response:
    api = settings.API_SETTINGS
    exempt_paths = PAYMENT_WEBHOOK_PATHS | MINIAPP_AUTH_PATHS | {
        path.strip() for path in api.CSRF_EXEMPT_PATHS.split(",") if path.strip()
    }
    if not api.CSRF_ENABLED or request.url.path in exempt_paths:
        return await call_next(request)

    token = get_csrf_token(request, settings)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        allowed_origins = {str(request.base_url).rstrip("/")} | set(
            api.CORS_ALLOWED_ORIGINS.split(",")
        )
        header = request.headers.get(api.CSRF_HEADER_NAME, "")
        if (
            (origin is not None and origin not in allowed_origins)
            or (
                origin is None and request.headers.get("sec-fetch-site") == "cross-site"
            )
            or token is None
            or not hmac.compare_digest(header.encode(), token.encode())
        ):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "CSRF validation failed"},
                headers={"Cache-Control": "no-store"},
            )

    response = await call_next(request)
    if token is None:
        token = create_csrf_token(settings)
        set_csrf_cookie(response, token, settings)
    response.headers[api.CSRF_HEADER_NAME] = token
    response.headers["Cache-Control"] = "no-store"
    return response


async def authentication_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    try:
        response = await call_next(request)
    except AuthenticationError as exc:
        if request.url.path in {"/users/auth/google", "/users/auth/telegram"}:
            logger.warning(
                "provider_login_rejected provider=%s reason=%s cause=%s",
                request.url.path.rsplit("/", 1)[-1],
                str(exc),
                type(exc.__cause__).__name__ if exc.__cause__ else "none",
            )
        code, detail = status.HTTP_401_UNAUTHORIZED, "Invalid or expired credentials"
        if isinstance(exc, UserBlockedError):
            code, detail = status.HTTP_403_FORBIDDEN, "User is blocked"
        elif isinstance(exc, AuthProviderUnavailableError):
            code, detail = (
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Authentication provider is unavailable",
            )
        elif isinstance(exc, AuthenticationConflictError):
            code, detail = (
                status.HTTP_409_CONFLICT,
                "Authentication conflict; retry with a new challenge",
            )
        elif isinstance(exc, AccountLinkConflictError):
            code, detail = status.HTTP_409_CONFLICT, str(exc)
        return JSONResponse(
            status_code=code,
            content={"detail": detail},
            headers={"Cache-Control": "no-store"},
        )
    except (
        PaymentProviderError,
        TelegramAPIError,
        RunPodError,
        ValidationError,
        PromoCodeError,
    ) as exc:
        code, detail = status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)
        if isinstance(exc, (PaymentProviderError, TelegramAPIError)):
            code, detail = (
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Payment provider is unavailable",
            )
        elif isinstance(exc, RunPodError):
            code, detail = (
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Generation provider is unavailable",
            )
        elif isinstance(exc, GenerationNotFoundError):
            code, detail = status.HTTP_404_NOT_FOUND, "Generation not found"
        elif isinstance(exc, WorkflowNotFoundError):
            code, detail = status.HTTP_404_NOT_FOUND, "Workflow not found"
        elif isinstance(exc, PresetNotFoundError):
            code, detail = status.HTTP_404_NOT_FOUND, "Preset not found"
        elif isinstance(exc, UnknownSystemSettingError):
            code, detail = status.HTTP_404_NOT_FOUND, str(exc)
        elif isinstance(exc, InsufficientCreditsError):
            code, detail = status.HTTP_402_PAYMENT_REQUIRED, str(exc)
        elif isinstance(exc, InvalidGenerationStateError):
            code, detail = status.HTTP_409_CONFLICT, str(exc)
        elif isinstance(exc, PaymentNotFoundError):
            code, detail = status.HTTP_404_NOT_FOUND, "Payment not found"
        elif isinstance(exc, InvalidPaymentSignatureError):
            code, detail = status.HTTP_401_UNAUTHORIZED, "Invalid payment signature"
        elif isinstance(exc, InvalidPaymentStateError):
            code, detail = (
                status.HTTP_409_CONFLICT,
                "Payment details conflict with the existing order",
            )
        elif isinstance(exc, PromoCodeNotFoundError):
            code, detail = status.HTTP_404_NOT_FOUND, "Promo code not found"
        elif isinstance(exc, PromoCodeConflictError):
            code, detail = status.HTTP_409_CONFLICT, str(exc)
        elif isinstance(exc, InvalidPromoCodeError):
            code, detail = status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)
        return JSONResponse(
            status_code=code,
            content={"detail": detail},
            headers={"Cache-Control": "no-store"},
        )
    if request.url.path in (
        "/users",
        "/admins",
        "/payments",
        "/generations",
        "/workflows",
        "/presets",
        "/referrals",
        "/promos",
    ) or request.url.path.startswith(
        (
            "/users/",
            "/admins/",
            "/payments/",
            "/generations/",
            "/workflows/",
            "/presets/",
            "/referrals/",
            "/promos/",
        )
    ):
        response.headers["Cache-Control"] = "no-store"
    return response
