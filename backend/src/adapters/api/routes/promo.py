from fastapi import APIRouter

from adapters.api.dependencies.promo import PromoServiceDep
from adapters.api.dependencies.user import CurrentUserDep
from adapters.api.schemas.promo import PromoRedemptionResponse, RedeemPromoCodeRequest

router = APIRouter(prefix="/promos", tags=["promos"])


@router.post("/redeem", response_model=PromoRedemptionResponse)
async def redeem_promo_code(
    data: RedeemPromoCodeRequest, user: CurrentUserDep, service: PromoServiceDep
) -> PromoRedemptionResponse:
    promo, balance = await service.redeem(user.id, data.code)
    return PromoRedemptionResponse(
        code=promo.code, credits=promo.credits, balance=balance
    )
