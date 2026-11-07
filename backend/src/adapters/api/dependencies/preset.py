from typing import Annotated

from fastapi import Depends

from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.database.repositiries import PresetRepository, WorkflowRepository
from domain.services.preset import PresetService


async def get_preset_service(manager: DatabaseManagerDep) -> PresetService:
    return PresetService(PresetRepository(manager), WorkflowRepository(manager))


PresetServiceDep = Annotated[PresetService, Depends(get_preset_service)]
