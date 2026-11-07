from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from adapters.api.cookies import delete_session_cookies, set_session_cookies
from adapters.api.dependencies.admin import AdminServiceDep, CurrentAdminDep
from adapters.api.dependencies.promo import PromoServiceDep
from adapters.api.dependencies.security import AdminRefreshTokenDep
from adapters.api.dependencies.settings import SettingsDep
from adapters.api.schemas.admin import (
    AdminLoginRequest,
    AdminResponse,
    AdminSessionResponse,
)
from adapters.api.schemas.promo import (
    AdminPromoCodeCreateRequest,
    AdminPromoCodeResponse,
    AdminPromoCodeUpdateRequest,
)
from domain.entities.admin import Admin
from domain.entities.auth import AdminSession
from domain.entities.promo import PromoCode

router = APIRouter(prefix="/admins", tags=["admins"])


@router.post("/auth/login", response_model=AdminSessionResponse)
async def login(
    data: AdminLoginRequest,
    response: Response,
    service: AdminServiceDep,
    settings: SettingsDep,
) -> AdminSession:
    session = await service.login(data.username, data.password)
    set_session_cookies(response, session, settings, admin=True)
    return session


@router.post("/auth/refresh", response_model=AdminSessionResponse)
async def refresh_session(
    response: Response,
    token: AdminRefreshTokenDep,
    service: AdminServiceDep,
    settings: SettingsDep,
) -> AdminSession:
    session = await service.refresh_session(token)
    set_session_cookies(response, session, settings, admin=True)
    return session


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    token: AdminRefreshTokenDep,
    service: AdminServiceDep,
    settings: SettingsDep,
) -> None:
    await service.logout(token)
    delete_session_cookies(response, settings, admin=True)


@router.get("/me", response_model=AdminResponse)
async def get_current_admin(admin: CurrentAdminDep) -> Admin:
    return admin


@router.post(
    "/promo-codes",
    response_model=AdminPromoCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_promo_code(
    data: AdminPromoCodeCreateRequest,
    admin: CurrentAdminDep,
    service: PromoServiceDep,
) -> PromoCode:
    return await service.create(
        data.code,
        data.credits,
        max_redemptions=data.max_redemptions,
        expires_at=data.expires_at,
        is_active=data.is_active,
    )


@router.get("/promo-codes", response_model=list[AdminPromoCodeResponse])
async def get_promo_codes(
    admin: CurrentAdminDep,
    service: PromoServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PromoCode]:
    return await service.list_codes(limit=limit, offset=offset)


@router.patch(
    "/promo-codes/{promo_code_id}", response_model=AdminPromoCodeResponse
)
async def update_promo_code(
    promo_code_id: UUID,
    data: AdminPromoCodeUpdateRequest,
    admin: CurrentAdminDep,
    service: PromoServiceDep,
) -> PromoCode:
    return await service.set_active(promo_code_id, data.is_active)
