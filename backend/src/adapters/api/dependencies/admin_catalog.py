from typing import Annotated

from fastapi import Depends

from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.database.repositiries.admin_catalog import AdminCatalogRepository
from domain.services.admin_catalog import AdminCatalogService


async def get_admin_catalog_service(
    manager: DatabaseManagerDep,
) -> AdminCatalogService:
    return AdminCatalogService(AdminCatalogRepository(manager))


AdminCatalogServiceDep = Annotated[
    AdminCatalogService, Depends(get_admin_catalog_service)
]
