from datetime import UTC, datetime
from uuid import UUID

from domain.entities.referral import Referral, ReferralStats
from domain.entities.user import User
from domain.exceptions.referral import InvalidReferralError
from domain.validators import NumberValidator
from ports.repositories.payment import (
    TransactionRepositoryInterface,
    WalletRepositoryInterface,
)
from ports.repositories.referral import ReferralRepositoryInterface


class ReferralService:
    def __init__(
        self,
        referrals: ReferralRepositoryInterface,
        wallets: WalletRepositoryInterface,
        transactions: TransactionRepositoryInterface,
        *,
        inviter_credits: int = 5,
        invitee_credits: int = 5,
    ) -> None:
        self._referrals = referrals
        self._wallets = wallets
        self._transactions = transactions
        self._inviter_credits = NumberValidator.validate_integer(
            inviter_credits, min_value=0, max_value=2**63 - 1
        )
        self._invitee_credits = NumberValidator.validate_integer(
            invitee_credits, min_value=0, max_value=2**63 - 1
        )

    async def attach(self, inviter: User, referred_user: User) -> Referral | None:
        if inviter.id == referred_user.id:
            raise InvalidReferralError("a user cannot refer themselves")
        existing = await self._referrals.get_by_referred_user(referred_user.id)
        if existing is not None:
            return existing
        if self._inviter_credits == 0 and self._invitee_credits == 0:
            return None
        return await self._referrals.create_referral(
            Referral(
                inviter_id=inviter.id,
                referred_user_id=referred_user.id,
                inviter_credits=self._inviter_credits,
                invitee_credits=self._invitee_credits,
            )
        )

    async def reward_for_purchase(self, referred_user_id: UUID) -> bool:
        """Award both sides once, after the referred user's first purchase."""
        referral = await self._referrals.get_by_referred_user_for_update(
            referred_user_id
        )
        if referral is None or referral.rewarded_at is not None:
            return False
        inviter_wallet = await self._wallets.get_by_user(referral.inviter_id)
        referred_wallet = await self._wallets.get_by_user(referred_user_id)
        if inviter_wallet is None or referred_wallet is None:
            raise InvalidReferralError("both accounts need a wallet")
        locked = {}
        for wallet_id in sorted({inviter_wallet.id, referred_wallet.id}, key=str):
            wallet = await self._wallets.get_for_update(wallet_id)
            if wallet is None:
                raise InvalidReferralError("wallet not found")
            locked[wallet.id] = wallet
        inviter_wallet = locked[inviter_wallet.id]
        referred_wallet = locked[referred_wallet.id]

        if referral.inviter_credits:
            await self._transactions.post_adjustment(
                inviter_wallet,
                amount=referral.inviter_credits,
                idempotency_key=f"referral:{referral.id}:inviter",
                description="Referral reward",
            )
        if referral.invitee_credits:
            await self._transactions.post_adjustment(
                referred_wallet,
                amount=referral.invitee_credits,
                idempotency_key=f"referral:{referral.id}:invitee",
                description="Welcome referral credit",
            )
        if not await self._referrals.mark_rewarded(referral.id, datetime.now(UTC)):
            raise InvalidReferralError("referral was already rewarded")
        return True

    async def stats(self, user: User) -> ReferralStats:
        invited_count, pending_count, credits_earned = await self._referrals.stats(
            user.id
        )
        return ReferralStats(
            referral_code=user.referral_code,
            invited_count=invited_count,
            credits_earned=credits_earned,
            referrer_credits=self._inviter_credits,
            invitee_credits=self._invitee_credits,
            pending_count=pending_count,
        )
