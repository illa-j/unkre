from typing import Annotated

from fastapi import Depends

from adapters.settings import Settings, get_settings


async def get_app_settings() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
