import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from domain.entities.auth import (
    AuthChallenge,
    AuthProvider,
    SocialIdentity,
    UserSession,
)
from domain.entities.user import User
from domain.exceptions.auth import (
    AccountLinkConflictError,
    InvalidCredentialsError,
    UserBlockedError,
)
from domain.exceptions.tokens import InvalidTokenError
from domain.services.referral import ReferralService
from domain.validators import NumberValidator, TextValidator
from ports.repositories.user import (
    UserRepositoryInterface,
    UserSessionRepositoryInterface,
)
from ports.security.tokens import JwtProviderInterface
from ports.services.oauth import OAuthServiceInterface


class UserService:
    def __init__(
        self,
        users: UserRepositoryInterface,
        sessions: UserSessionRepositoryInterface,
        oauth: OAuthServiceInterface,
        tokens: JwtProviderInterface,
        *,
        initial_credits: int = 15,
        initial_credits_provider: Callable[[], Awaitable[int]] | None = None,
        challenge_ttl: timedelta = timedelta(minutes=5),
        access_token_ttl: timedelta = timedelta(minutes=15),
        refresh_token_ttl: timedelta = timedelta(days=30),
        referrals: ReferralService | None = None,
    ) -> None:
        NumberValidator.validate_integer(initial_credits, min_value=0)
        for ttl in (challenge_ttl, access_token_ttl, refresh_token_ttl):
            if not isinstance(ttl, timedelta) or ttl < timedelta(seconds=1):
                raise ValueError("Token and challenge TTLs must be at least one second")
        self._users = users
        self._sessions = sessions
        self._oauth = oauth
        self._tokens = tokens
        self._initial_credits = initial_credits
        self._initial_credits_provider = initial_credits_provider
        self._challenge_ttl = challenge_ttl
        self._access_token_ttl = access_token_ttl
        self._refresh_token_ttl = refresh_token_ttl
        self._referrals = referrals

    async def create_challenge(self, provider: AuthProvider) -> AuthChallenge:
        provider = AuthProvider(provider)
        client_id = self._oauth.client_id(provider)
        nonce = secrets.token_urlsafe(32)
        await self._sessions.add_challenge(
            nonce, provider, datetime.now(UTC) + self._challenge_ttl
        )
        return AuthChallenge(
            nonce=nonce,
            client_id=client_id,
            expires_in=int(self._challenge_ttl.total_seconds()),
        )

    async def login_google(
        self, id_token: str, nonce: str, referral_code: str | None = None
    ) -> UserSession:
        return await self.login(AuthProvider.GOOGLE, id_token, nonce, referral_code)

    async def login_telegram(
        self, id_token: str, nonce: str, referral_code: str | None = None
    ) -> UserSession:
        return await self.login(AuthProvider.TELEGRAM, id_token, nonce, referral_code)

    async def login(
        self,
        provider: AuthProvider,
        id_token: str,
        nonce: str,
        referral_code: str | None = None,
    ) -> UserSession:
        provider = AuthProvider(provider)
        identity = await self._oauth.verify(provider, id_token, nonce)
        if identity.provider != provider:
            raise InvalidCredentialsError("Unexpected identity provider")
        if not await self._sessions.consume_challenge(nonce, provider):
            raise InvalidCredentialsError("Invalid or already used challenge")
        return await self._login_identity(identity, referral_code)

    async def login_miniapp(
        self, identity: SocialIdentity, referral_code: str | None = None
    ) -> UserSession:
        """Telegram MiniApp: initData is already verified by the caller."""
        if identity.provider != AuthProvider.TELEGRAM or identity.telegram_id is None:
            raise InvalidCredentialsError("Unexpected identity provider")
        return await self._login_identity(identity, referral_code)

    async def _login_identity(
        self, identity: SocialIdentity, referral_code: str | None
    ) -> UserSession:
        # Ідентифікуємо за Google sub або Telegram id, не зв'язуємо за email.
        user = await self._users.find_identity(identity)
        is_new_user = user is None
        if user is None:
            referrer = await self._find_referrer(referral_code)
            initial_credits = self._initial_credits
            if self._initial_credits_provider is not None:
                initial_credits = await self._initial_credits_provider()
            user = await self._users.register(identity, initial_credits)
            if referrer is not None and self._referrals is not None:
                await self._referrals.attach(referrer, user)
                refreshed = await self._users.get_user(user.id)
                if refreshed is not None:
                    user = refreshed
        else:
            self._check_user(user)
            user = await self._users.update_identity(user.id, identity)
        self._check_user(user)
        return await self._create_session(user, is_new_user=is_new_user)

    async def refresh_session(self, refresh_token: str) -> UserSession:
        user_id = self._decode_user_id(refresh_token, refresh=True)
        user = await self._require_user(user_id)
        if not await self._sessions.consume_refresh_token(user_id, refresh_token):
            raise InvalidCredentialsError("Invalid or already used refresh token")
        return await self._create_session(user)

    async def link_provider(
        self, user_id: UUID, provider: AuthProvider, id_token: str, nonce: str
    ) -> User:
        provider = AuthProvider(provider)
        identity = await self._oauth.verify(provider, id_token, nonce)
        if not await self._sessions.consume_challenge(nonce, provider):
            raise InvalidCredentialsError("Invalid or already used challenge")
        user = await self._require_user(user_id)
        existing = await self._users.find_identity(identity)
        if existing is not None and existing.id != user.id:
            raise AccountLinkConflictError(
                "This account is already linked to another user"
            )
        if provider == AuthProvider.GOOGLE:
            if user.google_sub is not None and user.google_sub != identity.subject:
                raise AccountLinkConflictError(
                    "A different Google account is already linked"
                )
        else:
            if identity.telegram_id is None:
                raise InvalidCredentialsError("Telegram identity has no user ID")
            if (
                user.telegram_id is not None
                and user.telegram_id != identity.telegram_id
            ):
                raise AccountLinkConflictError(
                    "A different Telegram account is already linked"
                )
        return await self._users.link_identity(user.id, identity)

    async def logout(self, refresh_token: str) -> None:
        user_id = self._decode_user_id(refresh_token, refresh=True)
        # Повторний logout чинного JWT є ідемпотентним; інші сесії не зачіпаємо.
        await self._sessions.consume_refresh_token(user_id, refresh_token)

    async def get_current_user(self, access_token: str) -> User:
        user_id = self._decode_user_id(access_token, refresh=False)
        return await self._require_user(user_id)

    async def _create_session(
        self, user: User, *, is_new_user: bool = False
    ) -> UserSession:
        claims = {"sub": str(user.id), "scope": "user"}
        access_token = self._tokens.create_access_token(claims, self._access_token_ttl)
        refresh_token = self._tokens.create_refresh_token(
            claims, self._refresh_token_ttl
        )
        await self._sessions.add_refresh_token(
            user.id, refresh_token, datetime.now(UTC) + self._refresh_token_ttl
        )
        return UserSession(
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(self._access_token_ttl.total_seconds()),
            is_new_user=is_new_user,
        )

    async def _find_referrer(self, referral_code: str | None) -> User | None:
        if self._referrals is None or not referral_code:
            return None
        code = referral_code.strip().lower()
        if len(code) != 24:
            return None
        referrer = await self._users.find_by_referral_code(code)
        if referrer is None or referrer.is_blocked:
            return None
        return referrer

    def _decode_user_id(self, token: str, *, refresh: bool) -> UUID:
        try:
            TextValidator.validate(token, max_length=16384)
            claims = (
                self._tokens.decode_refresh_token(token)
                if refresh
                else self._tokens.decode_access_token(token)
            )
            if claims.get("scope") != "user" or claims.get("type") != (
                "refresh" if refresh else "access"
            ):
                raise InvalidCredentialsError("Invalid user token")
            subject = TextValidator.validate(claims.get("sub"), max_length=36)
            return UUID(subject)
        except (InvalidTokenError, ValueError, TypeError, AttributeError) as exc:
            raise InvalidCredentialsError("Invalid user token") from exc

    async def _require_user(self, user_id: UUID) -> User:
        user = await self._users.get_user(user_id)
        if user is None:
            raise InvalidCredentialsError("Unknown user")
        self._check_user(user)
        return user

    @staticmethod
    def _check_user(user: User) -> None:
        if user.is_blocked:
            raise UserBlockedError("User is blocked")
