from datetime import timedelta
from typing import Annotated

from fastapi import Depends

from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.api.dependencies.security import (
    AdminAccessTokenDep,
    JwtProviderDep,
    PasswordHasherDep,
)
from adapters.api.dependencies.settings import SettingsDep
from adapters.database.repositiries.admin import AdminRepository
from adapters.database.repositiries.admin_refresh_token import (
    AdminRefreshTokenRepository,
)
from domain.entities.admin import Admin
from domain.services.admin import AdminService


async def get_admin_service(
    manager: DatabaseManagerDep,
    passwords: PasswordHasherDep,
    tokens: JwtProviderDep,
    settings: SettingsDep,
) -> AdminService:
    jwt = settings.JWT_TOKEN_SETTINGS
    return AdminService(
        admins=AdminRepository(manager),
        sessions=AdminRefreshTokenRepository(manager),
        passwords=passwords,
        tokens=tokens,
        access_token_ttl=timedelta(minutes=jwt.ACCESS_KEY_TIMEDELTA_MINUTES),
        refresh_token_ttl=timedelta(minutes=jwt.REFRESH_KEY_TIMEDELTA_MINUTES),
    )


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]


async def get_current_admin(
    token: AdminAccessTokenDep, service: AdminServiceDep
) -> Admin:
    return await service.get_current_admin(token)


CurrentAdminDep = Annotated[Admin, Depends(get_current_admin)]
