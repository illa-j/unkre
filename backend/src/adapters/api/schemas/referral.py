from adapters.api.schemas.common import ResponseModel


class ReferralStatsResponse(ResponseModel):
    referral_code: str
    invited_count: int
    credits_earned: int
    referrer_credits: int
    invitee_credits: int
    pending_count: int = 0
