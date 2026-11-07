from typing import Annotated

from fastapi import Depends

from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.api.dependencies.settings import SettingsDep
from adapters.system_settings import build_system_settings
from domain.services.system_setting import SystemSettingsService


async def get_system_settings_service(
    manager: DatabaseManagerDep, settings: SettingsDep
) -> SystemSettingsService:
    return build_system_settings(manager, settings)


SystemSettingsServiceDep = Annotated[
    SystemSettingsService, Depends(get_system_settings_service)
]
