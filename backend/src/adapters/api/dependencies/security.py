from typing import Annotated, Any

from fastapi import Depends, Request

from adapters.api.cookies import get_token_cookie
from adapters.api.dependencies.settings import SettingsDep
from adapters.security.password_hasher import Argon2PasswordHasher
from adapters.security.tokens import JwtProvider
from domain.exceptions.auth import InvalidCredentialsError
from domain.exceptions.tokens import InvalidTokenError
from ports.security.password_hasher import PasswordHasherInterface


async def get_password_hasher() -> PasswordHasherInterface:
    return Argon2PasswordHasher()


PasswordHasherDep = Annotated[PasswordHasherInterface, Depends(get_password_hasher)]


async def get_jwt_provider(settings: SettingsDep) -> JwtProvider:
    return JwtProvider(settings.JWT_TOKEN_SETTINGS)


JwtProviderDep = Annotated[JwtProvider, Depends(get_jwt_provider)]


async def get_access_token(request: Request, settings: SettingsDep) -> str:
    return get_token_cookie(request, settings.API_SETTINGS.CLIENT_ACCESS_TOKEN_COOKIE)


AccessTokenDep = Annotated[str, Depends(get_access_token)]


async def get_access_token_payload(
    token: AccessTokenDep, provider: JwtProviderDep
) -> dict[str, Any]:
    try:
        return provider.decode_access_token(token)
    except InvalidTokenError as exc:
        raise InvalidCredentialsError("Invalid access token") from exc


AccessTokenPayloadDep = Annotated[dict[str, Any], Depends(get_access_token_payload)]


async def get_refresh_token(request: Request, settings: SettingsDep) -> str:
    return get_token_cookie(request, settings.API_SETTINGS.CLIENT_REFRESH_TOKEN_COOKIE)


RefreshTokenDep = Annotated[str, Depends(get_refresh_token)]


async def get_admin_access_token(request: Request, settings: SettingsDep) -> str:
    return get_token_cookie(request, settings.API_SETTINGS.ADMIN_ACCESS_TOKEN_COOKIE)


AdminAccessTokenDep = Annotated[str, Depends(get_admin_access_token)]


async def get_admin_refresh_token(request: Request, settings: SettingsDep) -> str:
    return get_token_cookie(request, settings.API_SETTINGS.ADMIN_REFRESH_TOKEN_COOKIE)


AdminRefreshTokenDep = Annotated[str, Depends(get_admin_refresh_token)]


async def get_refresh_token_payload(
    token: RefreshTokenDep, provider: JwtProviderDep
) -> dict[str, Any]:
    try:
        return provider.decode_refresh_token(token)
    except InvalidTokenError as exc:
        raise InvalidCredentialsError("Invalid refresh token") from exc


RefreshTokenPayloadDep = Annotated[dict[str, Any], Depends(get_refresh_token_payload)]
