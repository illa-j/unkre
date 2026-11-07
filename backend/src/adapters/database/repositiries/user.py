from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from adapters.database.models import UserModel
from adapters.database.repositiries import CrudRepository
from domain.entities.auth import AuthProvider, SocialIdentity
from domain.entities.user import User
from domain.exceptions.auth import (
    AccountLinkConflictError,
    AuthenticationConflictError,
)
from ports import DatabaseManagerInterface


class UserRepository(CrudRepository[UserModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, UserModel)

    async def get_user(self, user_id: UUID) -> User | None:
        model = await self.get(user_id)
        return model.to_entity() if model else None

    async def _find_identity(self, identity: SocialIdentity) -> UserModel | None:
        condition = (
            UserModel.google_sub == identity.subject
            if identity.provider == AuthProvider.GOOGLE
            else UserModel.telegram_id == identity.telegram_id
        )
        return await self._db.scalar(select(UserModel).where(condition))

    async def find_identity(self, identity: SocialIdentity) -> User | None:
        model = await self._find_identity(identity)
        return model.to_entity() if model else None

    async def find_by_referral_code(self, code: str) -> User | None:
        model = await self._db.scalar(
            select(UserModel).where(UserModel.referral_code == code)
        )
        return model.to_entity() if model else None

    async def register(self, identity: SocialIdentity, credits: int) -> User:
        user = UserModel.from_entity(
            User(
                first_name=identity.first_name,
                last_name=identity.last_name,
                google_sub=(
                    identity.subject
                    if identity.provider == AuthProvider.GOOGLE
                    else None
                ),
                google_email=identity.email,
                telegram_id=identity.telegram_id,
                username=identity.username,
                photo_url=identity.photo_url,
                language_code=identity.language_code,
                credits=credits,
                last_active_at=datetime.now(UTC),
            )
        )
        try:
            async with self._db.db.begin_nested():
                await self.create(user)
        except IntegrityError as exc:
            raise AuthenticationConflictError from exc
        return user.to_entity()

    async def update_identity(self, user_id: UUID, identity: SocialIdentity) -> User:
        values: dict[str, object] = {
            "first_name": identity.first_name,
            "last_name": identity.last_name,
            "photo_url": identity.photo_url,
            "last_active_at": datetime.now(UTC),
        }
        if identity.provider == AuthProvider.GOOGLE:
            values["google_email"] = identity.email
        else:
            values["username"] = identity.username
        if identity.language_code is not None:
            values["language_code"] = identity.language_code
        for name in ("is_premium", "allows_write_to_pm", "added_to_attachment_menu"):
            value = getattr(identity, name)
            if value is not None:
                values[name] = value
        model = await self.update(user_id, values)
        if model is None:
            raise AuthenticationConflictError
        return model.to_entity()

    async def link_identity(self, user_id: UUID, identity: SocialIdentity) -> User:
        values: dict[str, object] = {}
        if identity.provider == AuthProvider.GOOGLE:
            values["google_sub"] = identity.subject
            if identity.email is not None:
                values["google_email"] = identity.email
        else:
            if identity.telegram_id is None:
                raise AccountLinkConflictError("Telegram identity has no user ID")
            values["telegram_id"] = identity.telegram_id
            if identity.username is not None:
                values["username"] = identity.username
        try:
            model = await self.update(user_id, values)
        except IntegrityError as exc:
            raise AccountLinkConflictError(
                "This account is already linked to another user"
            ) from exc
        if model is None:
            raise AccountLinkConflictError("User not found")
        return model.to_entity()
