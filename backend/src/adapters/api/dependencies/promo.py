from typing import Annotated

from fastapi import Depends

from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.database.repositiries.promo import (
    PromoCodeRepository,
    PromoRedemptionRepository,
)
from adapters.database.repositiries.transaction import TransactionRepository
from adapters.database.repositiries.user import UserRepository
from adapters.database.repositiries.wallet import WalletRepository
from domain.services.promo import PromoService


async def get_promo_service(manager: DatabaseManagerDep) -> PromoService:
    return PromoService(
        codes=PromoCodeRepository(manager),
        redemptions=PromoRedemptionRepository(manager),
        users=UserRepository(manager),
        wallets=WalletRepository(manager),
        transactions=TransactionRepository(manager),
    )


PromoServiceDep = Annotated[PromoService, Depends(get_promo_service)]
