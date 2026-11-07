import hashlib
import hmac
import secrets

from fastapi import Request, Response

from adapters.settings import Settings
from domain.entities.auth import AdminSession, UserSession
from domain.exceptions.auth import InvalidCredentialsError


def create_csrf_token(settings: Settings) -> str:
    value = secrets.token_hex(32)
    signature = hmac.new(
        settings.JWT_TOKEN_SETTINGS.SECRET_KEY_ACCESS.encode(),
        f"csrf:{value}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{value}.{signature}"


def get_csrf_token(request: Request, settings: Settings) -> str | None:
    token = request.cookies.get(settings.API_SETTINGS.CSRF_COOKIE_NAME, "")
    if len(token) != 129 or token[64] != ".":
        return None
    value, signature = token.split(".", 1)
    expected = hmac.new(
        settings.JWT_TOKEN_SETTINGS.SECRET_KEY_ACCESS.encode(),
        f"csrf:{value}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature.encode(), expected.encode()):
        return None
    return token


def set_csrf_cookie(response: Response, token: str, settings: Settings) -> None:
    api = settings.API_SETTINGS
    response.set_cookie(
        key=api.CSRF_COOKIE_NAME,
        value=token,
        max_age=settings.JWT_TOKEN_SETTINGS.REFRESH_KEY_TIMEDELTA_MINUTES * 60,
        path="/",
        domain=api.COOKIE_DOMAIN,
        secure=api.COOKIE_SECURE,
        httponly=False,
        samesite=api.COOKIE_SAMESITE,
    )


def get_token_cookie(request: Request, name: str) -> str:
    token = request.cookies.get(name)
    if not token or len(token) > 16384:
        raise InvalidCredentialsError("Missing or invalid token cookie")
    return token


def set_session_cookies(
    response: Response,
    session: UserSession | AdminSession,
    settings: Settings,
    *,
    admin: bool = False,
) -> None:
    api = settings.API_SETTINGS
    jwt = settings.JWT_TOKEN_SETTINGS
    for name, token, minutes in (
        (
            api.ADMIN_ACCESS_TOKEN_COOKIE if admin else api.CLIENT_ACCESS_TOKEN_COOKIE,
            session.access_token,
            jwt.ACCESS_KEY_TIMEDELTA_MINUTES,
        ),
        (
            api.ADMIN_REFRESH_TOKEN_COOKIE
            if admin
            else api.CLIENT_REFRESH_TOKEN_COOKIE,
            session.refresh_token,
            jwt.REFRESH_KEY_TIMEDELTA_MINUTES,
        ),
    ):
        response.set_cookie(
            key=name,
            value=token,
            max_age=minutes * 60,
            path="/",
            domain=api.COOKIE_DOMAIN,
            secure=api.COOKIE_SECURE,
            httponly=True,
            samesite=api.COOKIE_SAMESITE,
        )


def delete_session_cookies(
    response: Response, settings: Settings, *, admin: bool = False
) -> None:
    api = settings.API_SETTINGS
    names = (
        (api.ADMIN_ACCESS_TOKEN_COOKIE, api.ADMIN_REFRESH_TOKEN_COOKIE)
        if admin
        else (api.CLIENT_ACCESS_TOKEN_COOKIE, api.CLIENT_REFRESH_TOKEN_COOKIE)
    )
    for name in names:
        response.delete_cookie(
            key=name,
            path="/",
            domain=api.COOKIE_DOMAIN,
            secure=api.COOKIE_SECURE,
            httponly=True,
            samesite=api.COOKIE_SAMESITE,
        )
