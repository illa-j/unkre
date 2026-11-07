from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.api.dependencies.settings import SettingsDep
from adapters.database.repositiries import (
    GenerationRepository,
    TransactionRepository,
    UserRepository,
    WalletRepository,
    WorkflowRepository,
)
from adapters.runpod import RunPodClient
from domain.services.generation import GenerationService


async def get_runpod_client(settings: SettingsDep) -> AsyncIterator[RunPodClient]:
    async with RunPodClient(settings.RUNPOD_SETTINGS) as client:
        yield client


RunPodClientDep = Annotated[RunPodClient, Depends(get_runpod_client, scope="function")]


async def get_generation_service(
    manager: DatabaseManagerDep,
    runpod: RunPodClientDep,
) -> GenerationService:
    return GenerationService(
        GenerationRepository(manager),
        WorkflowRepository(manager),
        UserRepository(manager),
        runpod,
        wallets=WalletRepository(manager),
        transactions=TransactionRepository(manager),
    )


GenerationServiceDep = Annotated[GenerationService, Depends(get_generation_service)]
