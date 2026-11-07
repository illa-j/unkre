from ports.repositories.admin import (
    AdminRepositoryInterface,
    AdminSessionRepositoryInterface,
)
from ports.repositories.crud import CrudRepositoryInterface
from ports.repositories.generation import (
    GenerationRepositoryInterface,
    WorkflowRepositoryInterface,
)
from ports.repositories.payment import (
    PaymentRepositoryInterface,
    TransactionRepositoryInterface,
    WalletRepositoryInterface,
)
from ports.repositories.preset import PresetRepositoryInterface
from ports.repositories.promo import (
    PromoCodeRepositoryInterface,
    PromoRedemptionRepositoryInterface,
)
from ports.repositories.referral import ReferralRepositoryInterface
from ports.repositories.system_setting import SystemSettingRepositoryInterface
from ports.repositories.user import (
    UserRepositoryInterface,
    UserSessionRepositoryInterface,
)
