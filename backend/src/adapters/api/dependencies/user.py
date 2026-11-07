from datetime import timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from adapters.api.cookies import get_token_cookie
from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.api.dependencies.security import (
    AccessTokenDep,
    JwtProviderDep,
)
from adapters.api.dependencies.settings import SettingsDep
from adapters.api.dependencies.system_setting import SystemSettingsServiceDep
from adapters.database.repositiries.referral import ReferralRepository
from adapters.database.repositiries.transaction import TransactionRepository
from adapters.database.repositiries.user import UserRepository
from adapters.database.repositiries.user_session import UserSessionRepository
from adapters.database.repositiries.wallet import WalletRepository
from adapters.settings import get_settings
from domain.entities.user import User
from domain.services.oauth import OAuthService
from domain.services.referral import ReferralService
from domain.services.user import UserService
from ports.services.oauth import OAuthServiceInterface


@lru_cache(maxsize=1)
def get_oauth_service() -> OAuthServiceInterface:
    settings = get_settings().AUTH_SETTINGS
    return OAuthService(
        google_client_id=settings.GOOGLE_CLIENT_ID,
        telegram_client_id=settings.TELEGRAM_CLIENT_ID,
    )


OAuthServiceDep = Annotated[OAuthServiceInterface, Depends(get_oauth_service)]


async def get_referral_service(
    manager: DatabaseManagerDep,
    system_settings: SystemSettingsServiceDep,
) -> ReferralService:
    return ReferralService(
        referrals=ReferralRepository(manager),
        wallets=WalletRepository(manager),
        transactions=TransactionRepository(manager),
        inviter_credits=await system_settings.get_int("referral.inviter_credits"),
        invitee_credits=await system_settings.get_int("referral.invitee_credits"),
    )


ReferralServiceDep = Annotated[ReferralService, Depends(get_referral_service)]


async def get_user_service(
    manager: DatabaseManagerDep,
    oauth: OAuthServiceDep,
    tokens: JwtProviderDep,
    referrals: ReferralServiceDep,
    settings: SettingsDep,
    system_settings: SystemSettingsServiceDep,
) -> UserService:
    auth = settings.AUTH_SETTINGS
    jwt = settings.JWT_TOKEN_SETTINGS
    return UserService(
        users=UserRepository(manager),
        sessions=UserSessionRepository(manager),
        oauth=oauth,
        tokens=tokens,
        initial_credits=auth.USER_INITIAL_CREDITS,
        initial_credits_provider=lambda: system_settings.get_int(
            "registration.initial_credits"
        ),
        challenge_ttl=timedelta(seconds=auth.AUTH_CHALLENGE_TTL_SECONDS),
        access_token_ttl=timedelta(minutes=jwt.ACCESS_KEY_TIMEDELTA_MINUTES),
        refresh_token_ttl=timedelta(minutes=jwt.REFRESH_KEY_TIMEDELTA_MINUTES),
        referrals=referrals,
    )


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


async def get_current_user(token: AccessTokenDep, service: UserServiceDep) -> User:
    return await service.get_current_user(token)


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_optional_current_user(
    request: Request,
    service: UserServiceDep,
    settings: SettingsDep,
) -> User | None:
    """Return the signed-in user, or ``None`` when the browser has no session.

    A token cookie that exists but is invalid or expired still raises 401 so the
    client can refresh it; only a completely anonymous request gets ``None``.
    """
    api = settings.API_SETTINGS
    if not (
        request.cookies.get(api.CLIENT_ACCESS_TOKEN_COOKIE)
        or request.cookies.get(api.CLIENT_REFRESH_TOKEN_COOKIE)
    ):
        return None
    token = get_token_cookie(request, api.CLIENT_ACCESS_TOKEN_COOKIE)
    return await service.get_current_user(token)


OptionalCurrentUserDep = Annotated[User | None, Depends(get_optional_current_user)]
