import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from domain.entities.admin import Admin
from domain.entities.auth import AdminSession
from domain.exceptions.auth import AuthenticationConflictError, InvalidCredentialsError
from domain.exceptions.tokens import InvalidTokenError
from domain.validators import TextValidator
from ports.repositories.admin import (
    AdminRepositoryInterface,
    AdminSessionRepositoryInterface,
)
from ports.security.password_hasher import PasswordHasherInterface
from ports.security.tokens import JwtProviderInterface


class AdminService:
    def __init__(
        self,
        admins: AdminRepositoryInterface,
        sessions: AdminSessionRepositoryInterface,
        passwords: PasswordHasherInterface,
        tokens: JwtProviderInterface,
        *,
        access_token_ttl: timedelta = timedelta(minutes=15),
        refresh_token_ttl: timedelta = timedelta(days=30),
    ) -> None:
        for ttl in (access_token_ttl, refresh_token_ttl):
            if not isinstance(ttl, timedelta) or ttl < timedelta(seconds=1):
                raise ValueError("Token TTLs must be at least one second")
        self._admins = admins
        self._sessions = sessions
        self._passwords = passwords
        self._tokens = tokens
        self._access_token_ttl = access_token_ttl
        self._refresh_token_ttl = refresh_token_ttl

    async def login(self, username: str, password: str) -> AdminSession:
        try:
            username = TextValidator.validate(
                username, min_length=2, max_length=100, strip=True
            )
            TextValidator.validate(password, max_length=1024)
        except ValueError as exc:
            raise InvalidCredentialsError("Invalid admin credentials") from exc
        admin = await self._admins.find_by_username(username)
        if admin is None or admin.id is None or not admin.hashed_password:
            await asyncio.to_thread(self._passwords.hash_password, password)
            raise InvalidCredentialsError("Invalid admin credentials")
        valid = await asyncio.to_thread(
            self._passwords.verify_password, password, admin.hashed_password
        )
        if not valid:
            raise InvalidCredentialsError("Invalid admin credentials")
        if self._passwords.needs_rehash(admin.hashed_password):
            new_hash = await asyncio.to_thread(self._passwords.hash_password, password)
            await self._admins.update_password_hash(
                admin.id, admin.hashed_password, new_hash
            )
            admin.hashed_password = new_hash
        return await self._create_session(admin)

    async def create_admin(
        self, username: str, password: str, *, is_owner: bool = False
    ) -> Admin:
        username = TextValidator.validate(
            username, min_length=2, max_length=100, strip=True
        )
        TextValidator.validate(password, min_length=10, max_length=1024)
        if await self._admins.find_by_username(username) is not None:
            raise AuthenticationConflictError("Admin username is already taken")
        hashed = await asyncio.to_thread(self._passwords.hash_password, password)
        return await self._admins.create_admin(
            Admin(username=username, hashed_password=hashed, is_owner=is_owner)
        )

    async def refresh_session(self, refresh_token: str) -> AdminSession:
        admin_id = self._decode_admin_id(refresh_token, refresh=True)
        admin = await self._require_admin(admin_id)
        if not await self._sessions.consume_refresh_token(admin_id, refresh_token):
            raise InvalidCredentialsError("Invalid or already used refresh token")
        return await self._create_session(admin)

    async def logout(self, refresh_token: str) -> None:
        admin_id = self._decode_admin_id(refresh_token, refresh=True)
        await self._sessions.consume_refresh_token(admin_id, refresh_token)

    async def get_current_admin(self, access_token: str) -> Admin:
        admin_id = self._decode_admin_id(access_token, refresh=False)
        return await self._require_admin(admin_id)

    async def _create_session(self, admin: Admin) -> AdminSession:
        if admin.id is None:
            raise InvalidCredentialsError("Unknown admin")
        claims = {"sub": str(admin.id), "scope": "admin"}
        access_token = self._tokens.create_access_token(claims, self._access_token_ttl)
        refresh_token = self._tokens.create_refresh_token(
            claims, self._refresh_token_ttl
        )
        await self._sessions.add_refresh_token(
            admin.id, refresh_token, datetime.now(UTC) + self._refresh_token_ttl
        )
        return AdminSession(
            admin=admin,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(self._access_token_ttl.total_seconds()),
        )

    def _decode_admin_id(self, token: str, *, refresh: bool) -> UUID:
        try:
            TextValidator.validate(token, max_length=16384)
            claims = (
                self._tokens.decode_refresh_token(token)
                if refresh
                else self._tokens.decode_access_token(token)
            )
            if claims.get("scope") != "admin" or claims.get("type") != (
                "refresh" if refresh else "access"
            ):
                raise InvalidCredentialsError("Invalid admin token")
            subject = TextValidator.validate(claims.get("sub"), max_length=36)
            return UUID(subject)
        except (InvalidTokenError, ValueError, TypeError, AttributeError) as exc:
            raise InvalidCredentialsError("Invalid admin token") from exc

    async def _require_admin(self, admin_id: UUID) -> Admin:
        admin = await self._admins.get_admin(admin_id)
        if admin is None:
            raise InvalidCredentialsError("Unknown admin")
        return admin
