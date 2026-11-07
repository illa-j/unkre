from datetime import timedelta

from fastapi import APIRouter, Response, status

from adapters.api.cookies import delete_session_cookies, set_session_cookies
from adapters.api.dependencies.security import RefreshTokenDep
from adapters.api.dependencies.settings import SettingsDep
from adapters.api.dependencies.user import (
    CurrentUserDep,
    OptionalCurrentUserDep,
    UserServiceDep,
)
from adapters.api.schemas.user import (
    AccountLinkRequest,
    AuthChallengeRequest,
    SocialLoginRequest,
    TelegramWebAppLoginRequest,
    UserResponse,
    UserSessionResponse,
)
from domain.entities.auth import (
    AuthChallenge,
    AuthProvider,
    SocialIdentity,
    UserSession,
)
from domain.entities.user import User
from domain.security.telegram_webapp import verify_init_data

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/auth/challenge", response_model=AuthChallenge)
async def create_challenge(
    data: AuthChallengeRequest, service: UserServiceDep
) -> AuthChallenge:
    return await service.create_challenge(data.provider)


@router.post("/auth/google", response_model=UserSessionResponse)
async def login_google(
    data: SocialLoginRequest,
    response: Response,
    service: UserServiceDep,
    settings: SettingsDep,
) -> UserSession:
    session = await service.login_google(
        data.id_token, data.nonce, data.referral_code
    )
    set_session_cookies(response, session, settings)
    return session


@router.post("/auth/telegram", response_model=UserSessionResponse)
async def login_telegram(
    data: SocialLoginRequest,
    response: Response,
    service: UserServiceDep,
    settings: SettingsDep,
) -> UserSession:
    session = await service.login_telegram(
        data.id_token, data.nonce, data.referral_code
    )
    set_session_cookies(response, session, settings)
    return session


@router.post("/auth/telegram-webapp", response_model=UserSessionResponse)
async def login_telegram_webapp(
    data: TelegramWebAppLoginRequest,
    response: Response,
    service: UserServiceDep,
    settings: SettingsDep,
) -> UserSession:
    config = settings.BOT_SETTINGS
    verified = verify_init_data(
        data.init_data,
        config.TELEGRAM_BOT_TOKEN,
        ttl=timedelta(seconds=config.TELEGRAM_WEBAPP_AUTH_TTL_SECONDS),
    )
    identity = SocialIdentity(
        provider=AuthProvider.TELEGRAM,
        subject=str(verified.telegram_id),
        telegram_id=verified.telegram_id,
        first_name=verified.first_name,
        last_name=verified.last_name,
        username=verified.username,
        language_code=verified.language_code,
        photo_url=verified.photo_url,
        is_premium=verified.is_premium,
        allows_write_to_pm=verified.allows_write_to_pm,
        added_to_attachment_menu=verified.added_to_attachment_menu,
    )
    session = await service.login_miniapp(identity, data.referral_code)
    set_session_cookies(response, session, settings)
    return session


@router.post("/auth/refresh", response_model=UserSessionResponse)
async def refresh_session(
    response: Response,
    token: RefreshTokenDep,
    service: UserServiceDep,
    settings: SettingsDep,
) -> UserSession:
    session = await service.refresh_session(token)
    set_session_cookies(response, session, settings)
    return session


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    token: RefreshTokenDep,
    service: UserServiceDep,
    settings: SettingsDep,
) -> None:
    await service.logout(token)
    delete_session_cookies(response, settings)


@router.get("/session", response_model=UserResponse | None)
async def get_session(user: OptionalCurrentUserDep) -> User | None:
    """Anonymous-friendly session probe for the initial page load."""
    return user


@router.get("/me", response_model=UserResponse)
async def get_current_user(user: CurrentUserDep) -> User:
    return user


@router.post("/links/{provider}", response_model=UserResponse)
async def link_account(
    provider: AuthProvider,
    data: AccountLinkRequest,
    user: CurrentUserDep,
    service: UserServiceDep,
) -> User:
    return await service.link_provider(
        user.id, provider, data.id_token, data.nonce
    )
