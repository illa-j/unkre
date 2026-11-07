from fastapi import APIRouter

from adapters.api.dependencies.user import CurrentUserDep, ReferralServiceDep
from adapters.api.schemas.referral import ReferralStatsResponse
from domain.entities.referral import ReferralStats

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get("", response_model=ReferralStatsResponse)
async def get_referral_stats(
    user: CurrentUserDep, service: ReferralServiceDep
) -> ReferralStats:
    return await service.stats(user)
