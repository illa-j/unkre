from typing import Annotated

from fastapi import Depends, HTTPException, status

from adapters.api.dependencies.admin import CurrentAdminDep
from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.database.repositiries.admin_panel import AdminPanelRepository
from adapters.database.repositiries.transaction import TransactionRepository
from adapters.database.repositiries.user import UserRepository
from adapters.database.repositiries.wallet import WalletRepository
from domain.entities.admin import Admin
from domain.services.admin_panel import AdminPanelService


async def get_admin_panel_service(manager: DatabaseManagerDep) -> AdminPanelService:
    return AdminPanelService(
        AdminPanelRepository(manager),
        UserRepository(manager),
        WalletRepository(manager),
        TransactionRepository(manager),
    )


AdminPanelServiceDep = Annotated[AdminPanelService, Depends(get_admin_panel_service)]


async def get_owner(admin: CurrentAdminDep) -> Admin:
    if not admin.is_owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner access is required")
    return admin


OwnerDep = Annotated[Admin, Depends(get_owner)]
