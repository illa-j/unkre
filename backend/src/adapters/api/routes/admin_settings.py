from fastapi import APIRouter

from adapters.api.dependencies.admin import CurrentAdminDep
from adapters.api.dependencies.system_setting import SystemSettingsServiceDep
from adapters.api.schemas.system_setting import (
    SystemSettingResponse,
    UpdateSystemSettingRequest,
)
from domain.entities.system_setting import SystemSettingView

router = APIRouter(prefix="/admins/settings", tags=["admins"])


@router.get("", response_model=list[SystemSettingResponse])
async def get_system_settings(
    admin: CurrentAdminDep, service: SystemSettingsServiceDep
) -> list[SystemSettingView]:
    return await service.get_all()


@router.patch("/{key}", response_model=SystemSettingResponse)
async def update_system_setting(
    key: str,
    data: UpdateSystemSettingRequest,
    admin: CurrentAdminDep,
    service: SystemSettingsServiceDep,
) -> SystemSettingView:
    return await service.update(key, data.value, admin_id=admin.id)


@router.delete("/{key}", response_model=SystemSettingResponse)
async def reset_system_setting(
    key: str,
    admin: CurrentAdminDep,
    service: SystemSettingsServiceDep,
) -> SystemSettingView:
    return await service.reset(key, admin_id=admin.id)
