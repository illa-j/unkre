"""Owner account bootstrap from ADMIN_NAME / ADMIN_PASSWORD."""

import asyncio
from logging import getLogger

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from adapters.database import session_scope
from adapters.database.models import AdminModel
from adapters.security.password_hasher import Argon2PasswordHasher
from adapters.settings import Settings
from domain.entities.admin import Admin
from domain.validators import TextValidator

logger = getLogger(__name__)
MIN_PASSWORD_LENGTH = 10


async def ensure_bootstrap_admin(settings: Settings) -> None:
    """Create the owner account once, when the env credentials are configured.

    Safe for several API workers: a concurrent insert is reported as a no-op and
    never overwrites an existing password.
    """
    config = settings.ADMIN_SETTINGS
    if not config.configured:
        if config.ADMIN_NAME.strip() or config.ADMIN_PASSWORD:
            logger.warning(
                "Set both ADMIN_NAME and ADMIN_PASSWORD to bootstrap an administrator"
            )
        return
    try:
        username = TextValidator.validate(
            config.ADMIN_NAME, min_length=2, max_length=100, strip=True
        )
    except ValueError:
        logger.error("ADMIN_NAME must contain 2 to 100 characters; bootstrap skipped")
        return
    if len(config.ADMIN_PASSWORD) < MIN_PASSWORD_LENGTH:
        logger.error(
            "ADMIN_PASSWORD must be at least %s characters; bootstrap skipped",
            MIN_PASSWORD_LENGTH,
        )
        return
    try:
        async with session_scope() as session:
            existing = await session.scalar(
                select(AdminModel.id).where(AdminModel.username == username)
            )
            if existing is not None:
                return
            hashed = await asyncio.to_thread(
                Argon2PasswordHasher().hash_password, config.ADMIN_PASSWORD
            )
            session.add(
                AdminModel.from_entity(
                    Admin(username=username, hashed_password=hashed, is_owner=True)
                )
            )
        logger.info("Bootstrap administrator '%s' created", username)
    except IntegrityError:
        logger.info(
            "Bootstrap administrator '%s' was created by another process", username
        )
    except SQLAlchemyError as exc:
        logger.error(
            "Bootstrap administrator '%s' was not stored (%s)",
            username,
            type(exc).__name__,
        )
